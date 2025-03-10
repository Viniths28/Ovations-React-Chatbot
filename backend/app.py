import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from langchain.prompts import PromptTemplate  # Importing PromptTemplate

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

CORS(app)

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path="chroma_db")

# Initialize OpenAI embeddings
embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))

# Load CSV files from the "csv_files" folder
csv_folder = 'csv_files'
documents = []
for file in os.listdir(csv_folder):
    if file.endswith(".csv"):
        loader = CSVLoader(os.path.join(csv_folder, file), encoding='utf-8')
        documents.extend(loader.load())

# Split Documents into Chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
split_docs = text_splitter.split_documents(documents)

# Store Documents in ChromaDB
vector_store = Chroma(
    client=chroma_client,
    embedding_function=embeddings,
    persist_directory="chroma_db"
)
vector_store.add_documents(split_docs)

# Create retriever from Chroma vector store
retriever = vector_store.as_retriever(search_kwargs={"k": 10})

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-3.5-turbo", api_key=os.getenv("OPENAI_API_KEY"))

custom_prompt = PromptTemplate(
    template="""
    You are an AI assistant that provides clear, structured answers based on the provided documents.
    
    **Response Formatting Guidelines:**
    - Use bullet points for lists or key details.
    - Use paragraphs for explanations.
    - Keep responses concise and well-structured.
    - Maintain a user-friendly conversational tone.

    Question: {query}
    Answer:
    """,
    input_variables=["query"],
)



# Create a RetrievalQA chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"document_variable_name": "context"} 
)

def format_response(text):
    lines = text.split("\n")
    formatted_text = ""

    for line in lines:
        if line.strip().startswith("-"):  # Check for bullet points
            formatted_text += f"• {line.strip()[1:].strip()}\n"
        else:
            formatted_text += f"{line.strip()}\n"

    return formatted_text.strip()


# API Endpoint for Chat
@app.route("/chat", methods=["POST"])
def chat():
    user_query = request.json.get("query")
    try:
        response = qa_chain.invoke({"query": user_query})
        #formatted_response = format_response(response["result"])
        return jsonify({
            "response": response["result"]
            #"sources": [doc.page_content for doc in response["source_documents"]]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the Flask app
if __name__ == "__main__":
    app.run(port=5000, debug=True)
