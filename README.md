# llm_app_basics
<p align="center">
  <img src="https://github.com/Kamy-dev/llm_app_basics/assets/130248710/60a6d148-4db5-4bbe-b851-8fd00fb7accc" />
</p>

<br>

----

LLMを用いたアプリケーション開発において利用されるLangChainライブラリ、UIはStreamlitライブラリを利用した、Retrieval-Augmented Generation(RAG)を活用したLLMアプリケーション。  
会話履歴はボタン一つでNotionに保存可能。

----    
<br>

## 1. 機能

- RAGを用い、LLMが学習していない最新情報や社内文書等をアップロードし、そのデータを組み合わせてLLMに回答させる。
- Notion APIを利用し、LLMとの会話履歴をNotionに保管する。
- LLMの回答の根拠をコンソールで確認可能。

<br>

## 2. 目的

- RAGとは？という方向けに、RAGの有用性を理解してもらうこと。
- LangChainは多くの機能を持つが、まずはLangChainに触れたことのない方向けに、ローカルで動かしながら理解してもらうため。
- LLMはOpenAI社のChatGPT、VectorDBにはOSSのFAISSを利用している。
  LLMは特定のクラウドAIサービスを利用することも考慮したが、あるクラウドサービスを利用した場合、そのサービスに特化したコードになるため汎用性が低くなくなると考え、まずはRAGのコアの部分をシンプルに理解できるように、特定のクラウドAIサービスを敢えて利用しない方針で開発した。

<br>

## 3. 構成図

利用者とアプリ内部の挙動について図示する。  

<br>

<div align="center">
    <img src="https://github.com/Kamy-dev/llm_app_basics/assets/130248710/e73ef201-ad7b-4512-8597-93f56c2487c0" alt="構成図">
</div>

<br>
