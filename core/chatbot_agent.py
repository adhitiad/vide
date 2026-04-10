import os
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from data.mongodb_client import db
from logger import logger
import datetime

@tool
def request_new_video_generation(topic: str, platform: str, is_aggressive: bool, target_username: str) -> str:
    """Gunakan alat ini untuk memerintahkan sistem membuat/merender video baru. Anda WAJIB menyertakan 'target_username' dari konteks chat."""
    try:
        from tasks import run_rl_pipeline
        run_rl_pipeline.delay(owner_username=target_username)
        return f"Sistem sedang merender video tentang '{topic}' untuk platform {platform} atas nama user {target_username}."
    except Exception as e:
        return f"Gagal memicu pembuatan video: {e}"

@tool
def get_red_list_status(username: str) -> str:
    """Gunakan alat ini untuk mengecek ada berapa video klien di Daftar Merah."""
    count = db.published_videos.count_documents({
        "owner_username": username,
        "performance_status": "ACTION_REQUIRED_RED"
    })
    if count > 0:
        return f"Anda memiliki {count} video di Daftar Merah yang butuh persetujuan."
    return "Daftar Merah Anda bersih, tidak ada video yang tertahan."

@tool
def clear_blacklisted_videos() -> str:
    """Gunakan alat ini untuk menghapus log Daftar Hitam jika klien memintanya."""
    db.published_videos.delete_many({"performance_status": "BLACKLISTED"})
    return "Log Daftar Hitam telah dibersihkan."

tools = [request_new_video_generation, get_red_list_status, clear_blacklisted_videos]

def get_chatbot_response(user_message: str, username: str) -> dict:
    """Memproses pesan user, mengeksekusi alat jika perlu, dan merespons."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
         return {"response": "GROQ API KEY belum diatur.", "actions_taken": []}
         
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=api_key
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"Kamu adalah Asisten AI untuk platform AI-Clip-Hub. Klien saat ini: {username}. "
                   f"Tugasmu membantu klien mengelola pabrik konten video mereka. "
                   f"PENTING: Saat memanggil alat 'request_new_video_generation', kamu WAJIB memasukkan parameter 'target_username' degan nilai: '{username}'. "
                   f"Jawab dengan ramah, profesional, dan gunakan bahasa gaul/kasual Indonesia."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        result = agent_executor.invoke({"input": user_message})
        output_text = result.get("output", "Maaf, saya tidak mengerti permintaan Anda.")
        
        used_tools = [step[0].tool for step in result.get("intermediate_steps", [])]
        
        return {
            "response": output_text,
            "actions_taken": used_tools
        }
    except Exception as e:
        logger.error(f"Chatbot Error: {e}")
        return {"response": "Maaf, sistem AI sedang sibuk. Coba lagi nanti.", "actions_taken": []}
