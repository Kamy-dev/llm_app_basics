# llm_app_basics

![llm_app_basics](https://github.com/Kamy-dev/llm_app_basics/assets/130248710/584977ab-97cf-41f8-8307-0b7e7cd98a22)

----

LLMを用いたアプリケーション開発において利用されるLangChainライブラリ、UIはStreamlitライブラリを利用した、"基本のキ"を学べるRAGを活用したLLMアプリケーション。

----

## 1. 機能

- Retrieval-Augmented Generation(RAG)を用い、LLMが学習していない最新情報や社内文書等のPDFファイルをアップロードし、そのデータを組み合わせてLLMに回答させる。
- Notion APIを利用し、LLMとの会話履歴をNotionに保管できる。
- LLMの回答の根拠となったドキュメントの該当部分をコンソールで確認できる。

## 2. 目的

- RAGのメリット、デメリットを体感し、RAGが向いている事例を考えるきっかけを作るため。
- LangChainには数多くの機能が用意されているが、まずはLangChainに触れたことのない方向けに、ローカルで動かしながら理解してもらい、また自身で機能拡張などをしてもらい、RAGを用いたLLMアプリの基礎を理解できるアプリを目指した。
- LLMはOpenAI社のChatGPT, データソースとなるVectorDBにはOSSのFAISSを利用することで、RAGのコアの部分を理解できると考え、特定のクラウドAIサービスを敢えて利用しない方針で開発した。

## 3. 構成図

利用者とアプリ内部の挙動について図示する。
