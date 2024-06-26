import os
from dotenv import load_dotenv
import requests
import datetime
import streamlit as st

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

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# ページ全体の初期設定
def page_init_settings():
    st.set_page_config(
        # ページのタイトル
        page_title="RAG Application",
    )
    # サイドバーのタイトル
    st.sidebar.title("Menu")
        # サイドバーにLLM利用に掛かったコストを表示するためのリスト
    st.session_state.costs = []
    
# pdfアップロード画面の定義
def pdf_to_vector():
    st.header("PDF Upload")
    # アップローダー設定
    with st.container():
        pdf_text = get_pdf_contexts()
        if pdf_text:
            with st.spinner("Loading PDF ..."):
                # PDFのテキストをEmbeddingしFAISSに格納
                create_faiss(pdf_text)

# LLMに質問する画面
def page_query_gpt():
    st.header("Ask GPT with RAG!")
    # GPTモデルを指定する
    llm = select_gpt_model()
     # "Clear Conversations"ボタンが押されたら、会話履歴をリセットする
    if st.sidebar.button("Clear Conversations", type="primary"):
        st.session_state.messages = []

    # ユーザーの入力を監視
    if query:=st.chat_input("Please input your question"):
        # 会話履歴のステートが存在しない、もしくはNoneの場合にSystemMessageを加える
        if "messages" not in st.session_state or not st.session_state.messages:
            st.session_state.messages = [
                SystemMessage(content="You are a helpful assistant.")
        ]
        qa = qa_model(llm)
        if qa:
            with st.spinner("ChatGPT is creating text..."):
                answer, cost = ask_by_user(qa, query)
                st.session_state.costs.append(cost)

                # ユーザの入力を監視
                st.session_state.messages.append(HumanMessage(content=query))
                st.session_state.messages.append(AIMessage(content=answer["result"]))
                # 会話履歴をコンソールに出力
                pprint.pprint(st.session_state.messages)
                # ソースとなったドキュメントをコンソールに出力
                pprint.pprint(answer["source_documents"])

                # 会話履歴を画面に表示
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
    
    # Notionページを追加するサイドバー内のフォーム
    with st.sidebar.form("notion_add", clear_on_submit=True):
                title = st.text_input('Title')
                submitted = st.form_submit_button("Notionに保存")

    # Notionページに入力する会話履歴の取得
    if submitted:
        messages = st.session_state.get('messages', [])
        # 会話履歴をリストに格納する
        notion_contents = []
        for message in messages:
            if isinstance(message, HumanMessage):
                human_message=message.content
                notion_contents.append(f"あなた:  {human_message}")
            elif isinstance(message, AIMessage):
                ai_message=message.content
                notion_contents.append(f"GPT:  {ai_message}")
        notion_add(notion_contents, title)

# 利用するGPTモデルを指定し、最大トークン数をチェックする関数
def select_gpt_model():
    with st.sidebar:
        selection = st.radio(
            "Select GPT model:",
            ("gpt-3.5", "gpt-4")
        )
    if selection == "GPT-3.5":
        st.session_state.model_name = "gpt-3.5-turbo"
    elif selection == "gpt-4":
        st.session_state.model_name = "gpt-4"

    return ChatOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY, model=st.session_state.model_name)

# PDFファイルの内容を分割する関数
def get_pdf_contexts():
    # streamlitのファイルアップローダー設定
    uploaded_files = st.file_uploader(
        label="Upload your PDF:",
        type="pdf",
        accept_multiple_files=True
    )
    # PDFがアップロードされた時、PDFのテキストを処理する
    if uploaded_files:
        # PdfReaderでUploadしたPDFのテキストを読み取る
        for f in uploaded_files:
            pdf_reader = PdfReader(f)
        
        # テキストを改行文字で連結し、一つの文字列にする
        texts = '\n\n'.join([page.extract_text() for page in pdf_reader.pages])

        # テキストをチャンクに分割する定義
        # chunk_size=500 は、各チャンクのサイズが500文字になるようにテキストを分割する
        # chunk_overlap=0 は、各チャンク同士で重複する部分を持たないことを意味する
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=500,
            chunk_overlap=0
        )

        # 読み取ったテキストをチャンクに分割する
        text = text_splitter.split_text(texts)

        return text
    
    # PDFがアップロードされていない場合は何も返さない
    else:
       return None

# FAISSにEmbeddingしたテキストを保存、Index化しローカルストレージに格納する
def create_faiss(texts):
    # FAISSにOpenAIのembedding modelを使ってEmbeddingする
    db = FAISS.from_texts(texts=texts, embedding=embedding_model)

    # ローカルストレージにfaiss_dbというディレクトリを作成し、Embeddingデータ(index.faiss, index.pkl)を格納する
    db.save_local("./faiss_db", index_name="index")

# RetrievalQAにより、ユーザの質問とアップロードしたPDFの内容を組み合わせてLLMに質問する
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
        # indexから検索結果を何個取得するか指定
        search_kwargs = {"k":4}
    )

    return RetrievalQA.from_chain_type(
        llm = llm,
        chain_type = "stuff",
        retriever = retriever,
        # RetrievalQAがどのチャンクデータを取ってきたのかを確認するために、return_source_documentをTrueにする。
        return_source_documents=True,
        chain_type_kwargs=chain_type_kwargs,
        verbose = True
    )

# ユーザの質問に対する回答を返す
def ask_by_user(qa, query):
    try:
        with get_openai_callback() as cb:
            answer = qa({"query": query})
        return answer, cb.total_cost
    except Exception as e:
        print(f"An error occured: {e}")
        return None, 0

# Notionにテキストとタイトルが記載されたページを作成する
def notion_add(contents, title):
    today = datetime.date.today()
    title = title
    created_iso_format = today.isoformat()
    NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
    # ページを作成するNotionデータベースを指定する
    data_base_id = 'Your Notion Database ID'
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
    response.json()

def main():
    page_init_settings()
    with st.sidebar:
        selection = st.radio(
            "Please select:",
            ("Upload PDF", "Ask GPT")
        )
    if selection == "Upload PDF":
        pdf_to_vector()
    else:
        page_query_gpt()

    costs = st.session_state.get('costs', [])
    st.sidebar.markdown("## Costs")
    # st.session_state.costsリスト内の全てのコストを計算し、小数点以下5桁までの浮動小数点数で表示
    st.sidebar.markdown(f"**Total cost: ${sum(costs):.5f}**")
    # st.session_state.costsリスト内の各コストに対してループを行い、各コストを表示する。小数点以下5桁までの浮動小数点数で表示
    for cost in costs:
        st.sidebar.markdown(f"- ${cost:.5f}")

if __name__ == "__main__":
    main()