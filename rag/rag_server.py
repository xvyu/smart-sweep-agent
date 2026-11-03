"""
总结服务类: 用户提问, 搜索参考资料, 将提问和参考资料提交给模型, 让模型总结回复
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from Agent.rag.vector_store import VectorStoreService
from Agent.utils.prompt_loader import rag_summarize_prompt
from langchain_core.prompts import PromptTemplate
from Agent.model.factory import chat_model

def get_prompt(prompt):
    print("="*50)
    print(prompt.to_string())
    print("="*50)
    return prompt

class RagSummarizeServer:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = rag_summarize_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | get_prompt |self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str)->list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str)->str:
        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"[参考资料{counter}]: 参考资料: {doc.page_content} | 参考元数据: {doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context
            }
        )

if __name__ == '__main__':
    rag = RagSummarizeServer()
    res = rag.rag_summarize("小户型适合哪些扫地机器人")
    print(res)