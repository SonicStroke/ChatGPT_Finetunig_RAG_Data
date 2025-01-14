# -*- coding: utf-8 -*-
"""

Automatically generated by Colab.

"""

# 라이브러리 설치

!pip install langchain openai chromadb PyMuPDF langchain-openai langchain-community gradio tiktoken

# 구글드라이브 로드
from google.colab import drive
drive.mount('/content/drive')

# 파인튜닝 결과 모델 ID
FINE_TUNED_MODEL_ID = "ft:gpt-4o-2024-08-06:personal:math-chatbot-20241010-052526:AGg5AmyN"

MODEL_ID = FINE_TUNED_MODEL_ID
#if USE_FINE_TUNED_MODEL else "gpt-4o"#
#보안을 위해 OpenAI API Key는 ** 처리함.
OPENAI_KEY = 'sk-**'


# 이 폴더 안의 모든 pdf 찾아서 텍스트 추출
FOLDER_PATH = "/content/drive/MyDrive/논문연구 공유 폴더/RAG Data/"

import fitz  # PyMuPDF fitz는 PyMuPDF의 라이브러리로 PDF 파일 처리에 필요함
import glob # glob는 파일 시스템 내에서 특정 패턴에 맞는 파일을 찾는데 사용됨.
import os

def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

pdf_texts = []
for filename in glob.iglob(FOLDER_PATH + '**/*.pdf', recursive=True):
    file_path = os.path.join(FOLDER_PATH, filename)
    print(file_path)
    text = extract_text_from_pdf(file_path)
    pdf_texts.append({"id": filename, "text": text})

from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_KEY)

text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

documents = []
for pdf in pdf_texts:
    texts = text_splitter.split_text(pdf['text'])
    documents.extend([Document(page_content=text, metadata={"source": pdf['id']}) for text in texts])

vectorstore = Chroma.from_documents(documents, embeddings)

SYSTEM_MESSAGE = """너는 수학 상담 선생님이야.
앞으로 오는 질문에 친절하고 자세하게 답해.
대답은 다정한 반말로 해. 반드시 반말로 해야해. 존댓말을 사용하지 마.
답변은 상담전문가가 답변을 하듯 자연스러운 대화가되도록 해.
답변이 길어지면 단락을 나눠서 줄넘김을 해.
숫자를 열거하며 나열식의 대답은 절대금지. 열거식으로 대답하면 큰일난다. 절대로 열거식 또는 1, 2, 3 의 형태로 대답하지는 마.
상대방의 취약점을 끌어 낼 수 있도록 질문하며 대화를 이끌어가야해.
그렇다고 해서 모든 질문에 대한 대답에서 다시 질문하지는 마.
따뜻한 감성이 느껴지게 대답하고 친절하고 위로가 되는 말투도 함께해
같은 말을 계속 반복하지말고 위로가 되는 말은 여러 말을 바꿔가면서 해야해. 위로가 되는 말을 반드시 바꿔가면서 해야해."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from operator import itemgetter


def format_docs(docs):
    print("Refering docs : ", docs)
    return "\n\n".join(doc.page_content for doc in docs)

def format_chat_history(chat_history):
    formatted_history = []
    for human, ai in chat_history:
        formatted_history.append(('human', human))
        formatted_history.append(('ai', ai))

    return formatted_history

retriever = vectorstore.as_retriever()

USE_SYSTEM_MESSAGE_FINE_TUNED_RAG = True
USE_SYSTEM_MESSAGE_FINE_TUNED = True
USE_SYSTEM_MESSAGE = True

rag_chain_with_rag = (
    {
        "context": itemgetter('question') | RunnableLambda(retriever.get_relevant_documents) | RunnableLambda(format_docs),
        "question": itemgetter('question'),
        "chat_history": itemgetter('chat_history') | RunnableLambda(format_chat_history)
    }
    | ChatPromptTemplate.from_messages([
        *([("system", SYSTEM_MESSAGE)] if USE_SYSTEM_MESSAGE_FINE_TUNED_RAG else []),
        ("placeholder", "{chat_history}"),
        ("system", "아래 내용을 참고해서 답변해:\n{context}"),
        ("human", "{question}"),
    ])
    | ChatOpenAI(temperature=0, openai_api_key=OPENAI_KEY, model_name="gpt-4o")
    | StrOutputParser()
)

rag_chain_without_rag = (
    {
        "question": itemgetter('question'),
        "chat_history": itemgetter('chat_history') | RunnableLambda(format_chat_history)
    }
    | ChatPromptTemplate.from_messages([
        *([("system", SYSTEM_MESSAGE)] if USE_SYSTEM_MESSAGE_FINE_TUNED else []),
        ("placeholder", "{chat_history}"),
        ("human", "{question}"),
    ])
    | ChatOpenAI(temperature=0, openai_api_key=OPENAI_KEY, model_name=MODEL_ID)
    | StrOutputParser()
)


import gradio as gr
import traceback

def answer_question(message, history):
    try:
        response_with_rag = rag_chain_with_rag.invoke({"question": message, "chat_history": history})
        response_without_rag = rag_chain_without_rag.invoke({"question": message, "chat_history": history})
        response_plain = rag_chain_plain.invoke({"question": message, "chat_history": history})
        return f"RAG 적용 후: {response_with_rag}\n\nRAG 적용 전: {response_without_rag}\n\n원본: {response_plain}"        
    except Exception as e:
        return f"오류가 발생했습니다. 다시 시도해주세요.\n\n{traceback.format_exc()}"

interface = gr.ChatInterface(fn=answer_question, title="수학 상담 친구", description="수학에 대한 고민 또는 질문 방법 등 수학과 관련된 모든 것을 질문해 보세요.")

interface.launch(share=True, debug=True)