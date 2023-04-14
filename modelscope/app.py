import os

import gradio as gr
import nltk
import sentence_transformers
import torch
from langchain.chains import RetrievalQA
from langchain.document_loaders import UnstructuredFileLoader
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.vectorstores import FAISS

from chatglm_llm import ChatGLM

nltk.data.path.append('./nltk_data')

DEVICE = "cpu"

embedding_model_dict = {
    "ernie-tiny": "nghuyong/ernie-3.0-nano-zh",
    "ernie-base": "nghuyong/ernie-3.0-xbase-zh",
    "text2vec-base": "shibing624/text2vec-base-chinese",
}


def init_knowledge_vector_store(embedding_model, filepath):

    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model_dict[embedding_model], )
    embeddings.client = sentence_transformers.SentenceTransformer(
        embeddings.model_name, device=DEVICE)

    loader = UnstructuredFileLoader(filepath, mode="elements")
    docs = loader.load()

    vector_store = FAISS.from_documents(docs, embeddings)
    return vector_store


def get_knowledge_based_answer(
    query,
    vector_store,
    VECTOR_SEARCH_TOP_K,
    chat_history=[],
    history_len=3,
    temperature=0.01,
    top_p=0.9,
):
    prompt_template = """基于以下已知信息，简洁和专业的来回答用户的问题。
        如果无法从中得到答案，请说 "根据已知信息无法回答该问题" 或 "没有提供足够的相关信息"，不允许在答案中添加编造成分，答案请使用中文。

        已知内容:
        {context}

        问题:
        {question}"""
    prompt = PromptTemplate(template=prompt_template,
                            input_variables=["context", "question"])

    chatLLM = ChatGLM()

    chatLLM.history = chat_history[-history_len:] if history_len > 0 else []
    chatLLM.temperature = temperature
    chatLLM.top_p = top_p

    knowledge_chain = RetrievalQA.from_llm(
        llm=chatLLM,
        retriever=vector_store.as_retriever(
            search_kwargs={"k": VECTOR_SEARCH_TOP_K}),
        prompt=prompt)

    knowledge_chain.return_source_documents = True
    result = knowledge_chain({"query": query})

    return result['result']


def clear_session():
    return '', None


def predict(input,
            embedding_model,
            file_obj,
            VECTOR_SEARCH_TOP_K,
            history_len,
            temperature,
            top_p,
            history=None):
    if history == None:
        history = []
    print(file_obj.name)
    vector_store = init_knowledge_vector_store(embedding_model, file_obj.name)

    resp = get_knowledge_based_answer(
        query=input,
        vector_store=vector_store,
        VECTOR_SEARCH_TOP_K=VECTOR_SEARCH_TOP_K,
        chat_history=history,
        history_len=history_len,
        temperature=temperature,
        top_p= top_p,
    )
    print(resp)
    history.append((input, resp))
    return '', history, history


if __name__ == "__main__":
    block = gr.Blocks()
    with block as demo:
        gr.Markdown("""<h1><center>LangChain-ChatLLM-Webui</center></h1>
        <center><font size=3>
        本项目基于LangChain和大型语言模型系列模型, 提供基于本地知识的自动问答应用. <br>
        目前项目提供基于<a href='https://github.com/THUDM/ChatGLM-6B' target="_blank">ChatGLM-6B </a>的LLM和包括GanymedeNil/text2vec-large-chinese、nghuyong/ernie-3.0-base-zh、nghuyong/ernie-3.0-nano-zh在内的多个Embedding模型, 支持上传 txt、docx、md 等文本格式文件. <br>
        后续将提供更加多样化的LLM、Embedding和参数选项供用户尝试, 欢迎关注<a href='https://github.com/thomas-yanxin/LangChain-ChatGLM-Webui' target="_blank">Github地址</a>.
        </center></font>
        """)
        with gr.Row():
            with gr.Column(scale=1):
                embedding_model = gr.Dropdown([
                    "ernie-tiny", "ernie-base", "text2vec-base"
                ],
                                              label="Embedding model",
                                              value="ernie-tiny")

                file = gr.File(label='请上传知识库文件',
                               file_types=['.txt', '.md', '.docx'])


                VECTOR_SEARCH_TOP_K = gr.Slider(1,
                                                20,
                                                value=6,
                                                step=1,
                                                label="vector search top k",
                                                interactive=True)

                HISTORY_LEN = gr.Slider(0,
                                        5,
                                        value=3,
                                        step=1,
                                        label="history len",
                                        interactive=True)

                temperature = gr.Slider(0,
                                        1,
                                        value=0.01,
                                        step=0.011,
                                        label="temperature",
                                        interactive=True)
                top_p = gr.Slider(0,
                                1,
                                value=0.9,
                                step=0.1,
                                label="top_p",
                                interactive=True)

            with gr.Column(scale=4):
                chatbot = gr.Chatbot(label='ChatLLM').style(height=400)
                message = gr.Textbox(label='请输入问题')
                state = gr.State()

                
                with gr.Row():
                    clear_history = gr.Button("🧹 清除历史对话")
                    send = gr.Button("🚀 发送")

                    send.click(predict,
                            inputs=[
                                message, embedding_model, file, VECTOR_SEARCH_TOP_K,
                                HISTORY_LEN, temperature, top_p, state
                            ],
                            outputs=[message, chatbot, state])
                    clear_history.click(fn=clear_session,
                                        inputs=[],
                                        outputs=[chatbot, state],
                                        queue=False)

                    message.submit(predict,
                                inputs=[
                                    message, embedding_model, file, VECTOR_SEARCH_TOP_K,
                                    HISTORY_LEN, temperature, top_p, state
                                ],
                                outputs=[message, chatbot, state])
        gr.Markdown("""提醒：<br>
        1. 请勿上传或输入敏感内容，否则输出内容将被平台拦截返回error. <br>
        2. 使用时请先上传自己的知识文件，并且文件中不含某些特殊字符，否则将返回error. <br>
        3. 有任何使用问题，请通过[问题交流区](https://modelscope.cn/studios/thomas/ChatYuan-test/comment)或[Github Issue区](https://github.com/thomas-yanxin/LangChain-ChatGLM-Webui/issues)进行反馈. <br>
        """)
    demo.queue().launch(share=True)