import os
from dotenv import load_dotenv
import requests
import datetime
import streamlit as st

from langchain_community.llms.openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.callbacks import get_openai_callback
from langchain_core.prompts import PromptTemplate
import pprint

from pypdf import PdfReader
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.schema import ( SystemMessage, HumanMessage, AIMessage)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
os.environ["LANGCHAIN_TRACING_V2"] = "True"

embedding_model = OpenAIEmbeddings()

# ページ全体の初期設定
def page_init_settings():
    st.set_page_config(
        # ページのタイトル
        page_title="RAG Application",
        # TODO: Get Helpは使い方を簡単に説明する部分のため、GitHub repogitoryのリンクからREADMEを読んでもらう
        # menu_items={
        #   "Get Help": "GitHubリンク"
        # }
    )
    # サイドバーのタイトル
    st.sidebar.title("Menu")
    st.session_state.costs = []
    
# pdfアップロード画面の定義
def page_pdf_upload_and_build_vector_db():
    st.header("PDF Upload")
    container = st.container()
    with container:
        pdf_text = get_pdf_contexts()
        if pdf_text:
            # FAISSに渡すテキストと、Notion APIに渡すアップロードファイル名を格納
            with st.spinner("Loading PDF ..."):
                create_faiss(pdf_text)


# GPTに質問する画面の定義
def page_query_gpt():
    st.header("Ask GPT with RAG!")
    # GPTモデルを指定する関数を変数llmに代入する
    llm = select_gpt_model()
    if st.sidebar.button("Clear Conversations", type="primary"):
        st.session_state.messages = []

    # チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = [
            SystemMessage(content="You are a helpful assistant.")
        ]

    # ユーザーの入力を監視
    if query:=st.chat_input("Please input your question"):
        qa = qa_model(llm)
        if qa:
            with st.spinner("ChatGPT is creating text..."):
                answer, cost = ask_by_user(qa, query)
                pprint.pprint(answer)
                st.session_state.costs.append(cost)

                # ユーザの入力を監視
                st.session_state.messages.append(HumanMessage(content=query))
                pprint.pprint(st.session_state.messages)
                st.session_state.messages.append(AIMessage(content=answer["result"]))
                pprint.pprint(st.session_state.messages)
                # ソースとなるドキュメントをコンソールに出力させる
                pprint.pprint(answer["source_documents"])

                # チャット履歴の表示
                messages = st.session_state.get('messages', [])
                for message in messages:
                    if isinstance(message, AIMessage):
                        with st.chat_message('assistant'):
                            st.markdown(message.content)
                    elif isinstance(message, HumanMessage):
                        with st.chat_message('user'):
                            st.markdown(message.content)  
        else:
            answer = None
    
    with st.sidebar.form("notion_add", clear_on_submit=True):
                name = st.text_input('Title')
                submitted = st.form_submit_button("Notionに保存")

    if submitted:
        messages = st.session_state.get('messages', [])
        notion_contents = []
        for i in range(len(messages)):
            if i % 2 == 1:
                # HumanMessageを抜き出し、Notionのコンテンツに格納する
                human_message = messages[i].content
                notion_contents.append(f"あなた: {human_message}")
            elif i % 2 == 0 and i !=0:
                # AIMessageを抜き出し、Notionのコンテンツに格納する
                ai_message = messages[i].content
                notion_contents.append(f"GPT: {ai_message}")
            pprint.pprint(notion_contents)
        notion_add(notion_contents, name)

# 利用するGPTモデルを指定し、最大トークン数をチェックする関数
def select_gpt_model():
    with st.sidebar:
        selection = st.radio(
            "Select GPT model:",
            ("GPT-3.5", "gpt-4")
        )
    if selection == "GPT-3.5":
        st.session_state.model_name = "gpt-3.5-turbo"
    elif selection == "gpt-4":
        st.session_state.model_name = "gpt-4"

    # ユーザのクエリの本文を300トークンと仮定し、指定したGPTモデルの最大トークン数から引き、max tokenを確認する。
    st.session_state.max_token = OpenAI.modelname_to_contextsize(st.session_state.model_name) - 300
    return ChatOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY, model=st.session_state.model_name)

# PDFファイルの内容を分割する関数
def get_pdf_contexts():
    # streamlitのファイルアップローダー設定
    uploaded_files = st.file_uploader(
        label="Upload your PDF:",
        type="pdf",
        accept_multiple_files=True
    )
    # PDFがアップロードされた際に、そのPDFのテキストを読み取り分割する
    if uploaded_files:
        # PdfReaderでUploadしたPDFのテキストを読み取る。
        for f in uploaded_files:
            # Notionのタイトルはアップロードファイル名にするための処理
            pdf_reader = PdfReader(f)
        # セパレータをPDFのpage単位で付与する。
        texts = '\n\n'.join([page.extract_text() for page in pdf_reader.pages])
        # PDFのテキストをtext_splitterの設定(chunkサイズやオーバーラップの定義)を定義する。
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            #model_name=st.session_state.emb_model_name,
            chunk_size=1000,
            chunk_overlap=0
        )
        # 定義に従って、PdfReaderで読み取ったテキストを分割する。
        text = text_splitter.split_text(texts)
        return text
    # PDFがアップロードされていない場合は何も返さない。
    else:
       return None

# FAISSにEmbedded textを保存し、それをローカルストレージに格納する関数
def create_faiss(texts):
    # FAISSに保存するテキストデータをsplitted_text変数に格納する。
    # FAISSにOpenAIのembedding modelを使ってベクトル化し保管する。つまり変数"db"にはembeddingされたテキストが格納される。
    db = FAISS.from_texts(texts=texts, embedding=embedding_model)

    # ローカルストレージにfaiss_dbというディレクトリを作成し、embeddingされたデータ(thesis.faiss, thesis.pkl)を格納させる。
    db.save_local("./faiss_db", index_name="index")

# ユーザのqaをRetrievalQAがVectorDB(FAISS)のデータと併せて回答を作成する。
def qa_model(llm):
    prompt_template = """あなたは分からないことは分からないと伝え、分かることは初心者でも分かるように分かりやすく回答してくれるアシスタントです。
    丁寧に日本語で答えてください。
    もし以下の情報が、探している情報に関連していない場合、そのトピックに関する自身の知識を元に回答してください。
    
    {context}

    質問: {question}
    回答(日本語): """

    prompt_qa = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    chain_type_kwargs = {"prompt": prompt_qa}

    load_db = FAISS.load_local(
        "./faiss_db",
        allow_dangerous_deserialization=True,
        index_name="index",
        embeddings=embedding_model
    )
    retriever = load_db.as_retriever(
        # 何個の文書を取得するか設定
        search_kwargs = {"k":4}
    )
    # 
    return RetrievalQA.from_chain_type(
        llm = llm,
        chain_type = "stuff",
        retriever = retriever,
        # RetrievalQAがどのチャンクデータを取ってきたのかを確認するために、return_source_documentをTrueにする。
        return_source_documents=True,
        chain_type_kwargs=chain_type_kwargs,
        verbose = True
    )

# qaにはqa_model(llm)が格納される。つまり、RetrievalQAインスタンスが返り値。
# →「RetrievalQA.from_chain_type(query)」となる。(queryにはユーザのinputが入る。)
def ask_by_user(qa, query):
    try:
        with get_openai_callback() as cb:
            answer = qa({"query": query})
            #answer = qa(query)
            print(answer["result"])
        return answer, cb.total_cost
    except Exception as e:
        print(f"An error occured: {e}")
        return None, 0

# Notion API

# Notionにテキストとタイトルが記載されたページを作成する
def notion_add(contents, title):
    today = datetime.date.today()
    title = title
    created_iso_format = today.isoformat()
    NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
    data_base_id = '84b10ff627df419d9c5083b914d90eb9'
    #tag_name = "日記"
    #detail_text = "最新動向"
    content = "\n".join(contents)

    url = 'https://api.notion.com/v1/pages'

    headers = {
        "Accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {NOTION_API_TOKEN}"
    }

    payload = {
        "parent": {
            "database_id": data_base_id
        },
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ],
            },
            "Created at": {
                "type": "date",
                "date": {
                    "start": created_iso_format
                }
            },
        },
        "children": [
            {
                "object": 'block',
                "type": 'heading_2',
                "heading_2": {
                    "rich_text": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ],
                }
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": content,
                                
                            }
                        }
                    ],
                    "color": "default"
                }
            },
        ],
    }

    response = requests.post(url, json=payload, headers=headers)
    result_dict = response.json()
    print(result_dict)

def main():
    page_init_settings()

    with st.sidebar:
        selection = st.radio(
            "Please select:",
            ("Upload PDF", "Ask GPT")
        )
    if selection == "Upload PDF":
        page_pdf_upload_and_build_vector_db()
    else:
        page_query_gpt()

    costs = st.session_state.get('costs', [])
    st.sidebar.markdown("## Costs")
    # st.session_state.costs = []のリスト内の全てのコストを計算し、小数点以下5桁までの浮動小数点数で表示
    st.sidebar.markdown(f"**Total cost: ${sum(costs):.5f}**")
    # st.session_state.costs = []のリスト内の各コストに対してループを行い、各コストを表示する。小数点以下5桁までの浮動小数点数で表示
    for cost in costs:
        st.sidebar.markdown(f"- ${cost:.5f}")

if __name__ == "__main__":
    main()