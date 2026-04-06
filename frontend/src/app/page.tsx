"use client";

import { Button } from "@/components/ui/button";
import {
  Activity,
  RefreshCw,
  Send,
  Server,
  Terminal,
  Tv,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type TopicInfo = {
  name: string;
  score: number;
  times_chosen: number;
};

type PublishedVideo = {
  platform: string;
  topic_name: string;
  video_url: string;
  published_at: string;
};

export default function DashboardPage() {
  const [topics, setTopics] = useState<TopicInfo[]>([]);
  const [videos, setVideos] = useState<PublishedVideo[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // WebSockets connections
    const wsStats = new WebSocket(`ws://localhost:8000/ws/stats`);
    const wsPublished = new WebSocket(`ws://localhost:8000/ws/published`);
    const wsLogs = new WebSocket(`ws://localhost:8000/ws/logs`);

    wsStats.onopen = () => setIsConnected(true);
    wsStats.onclose = () => setIsConnected(false);
    wsStats.onerror = () => setIsConnected(false);

    wsStats.onmessage = (event) => setTopics(JSON.parse(event.data));
    wsPublished.onmessage = (event) => setVideos(JSON.parse(event.data));

    wsLogs.onmessage = (event) => {
      setLogs((prev) => {
        const newLogs = [...prev, event.data];
        return newLogs.slice(-200); // keep last 200 logs
      });
    };

    return () => {
      wsStats.close();
      wsPublished.close();
      wsLogs.close();
    };
  }, []);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const triggerPipeline = async () => {
    try {
      await fetch("http://localhost:8000/api/actions/trigger-rl", {
        method: "POST",
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-200 p-4 md:p-8 font-sans selection:bg-indigo-500/30">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#030712] to-pink-900/10 pointer-events-none -z-10" />

      {/* HEADER */}
      <header className="flex flex-col md:flex-row justify-between items-center gap-6 mb-10">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-fuchsia-600 rounded-2xl flex items-center justify-center text-white shadow-[0_0_30px_rgba(99,102,241,0.4)] rotate-3">
            <Zap size={32} fill="currentColor" />
          </div>
          <div>
            <h1 className="text-4xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-pink-300">
              AI-CLIP-HUB
            </h1>
            <p className="text-xs font-bold text-indigo-400 tracking-[0.2em] uppercase mt-1">
              God-Tier UGC Automation Engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <Button
            onClick={triggerPipeline}
            className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl text-sm font-semibold transition-all shadow-lg hover:border-indigo-400/50"
          >
            <Send size={16} className="text-indigo-400" /> Trigger RL Manually
          </Button>

          <div
            className={`flex items-center gap-3 px-5 py-2 rounded-2xl text-sm font-bold border backdrop-blur-md shadow-lg ${
              isConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-red-500/10 text-red-400 border-red-500/30"
            }`}
          >
            <Server size={18} />
            <span>
              {isConnected ? "SYSTEM OPERATIONAL" : "CONNECTION LOST"}
            </span>
            {isConnected && (
              <span className="relative flex h-3 w-3 ml-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* TOPICS LEADERBOARD */}
        <section className="col-span-1 lg:col-span-4 flex flex-col gap-4">
          <div className="bg-slate-900/40 border border-indigo-500/10 rounded-2xl p-6 backdrop-blur-xl h-full flex flex-col shadow-2xl relative overflow-hidden">
            {/* Glow decor */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 blur-[50px] -z-10 rounded-full"></div>

            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
              <Activity className="text-indigo-400" size={20} />
              <h2 className="text-xl font-bold tracking-tight text-slate-100">
                Topic Intel
              </h2>
              <span className="ml-auto text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded font-black tracking-widest uppercase">
                RL ENVT
              </span>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
              {topics.map((topic, i) => (
                <div
                  key={topic.name}
                  className="flex justify-between items-center p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-transparent hover:border-indigo-500/20 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`font-mono text-lg font-black ${i === 0 ? "text-yellow-400" : i === 1 ? "text-slate-300" : i === 2 ? "text-orange-400" : "text-slate-600"}`}
                    >
                      #{i + 1}
                    </span>
                    <div>
                      <h3 className="font-semibold text-slate-200 group-hover:text-indigo-300 transition-colors">
                        {topic.name}
                      </h3>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        SELECTED: {topic.times_chosen}X
                      </p>
                    </div>
                  </div>
                  <div className="text-indigo-400 font-mono font-bold bg-indigo-950/30 px-2 py-1 rounded-md">
                    {topic.score.toFixed(2)}
                  </div>
                </div>
              ))}
              {topics.length === 0 && (
                <p className="text-slate-500 text-sm text-center py-10 italic">
                  Scanning nodes...
                </p>
              )}
            </div>
          </div>
        </section>

        {/* LOGS AND PUBLICATIONS */}
        <section className="col-span-1 lg:col-span-8 flex flex-col gap-8">
          {/* TERMINAL */}
          <div className="bg-black/60 border border-white/5 rounded-2xl p-1 flex flex-col h-[400px] shadow-2xl relative">
            <div className="flex items-center px-4 py-3 bg-white/5 border-b border-white/5 rounded-t-xl gap-3">
              <Terminal size={18} className="text-slate-400" />
              <h2 className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
                Neural Engine Logs
              </h2>
              <div className="ml-auto flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500/40"></div>
                <div className="w-3 h-3 rounded-full bg-amber-500/40"></div>
                <div className="w-3 h-3 rounded-full bg-emerald-500/40"></div>
              </div>
            </div>
            <div
              ref={logContainerRef}
              className="flex-1 p-4 overflow-y-auto font-mono text-xs sm:text-sm whitespace-pre-wrap leading-relaxed custom-scrollbar"
            >
              {logs.map((log, i) => {
                let badgeClass = "text-slate-400 opacity-90";
                if (log.includes("ERROR") || log.includes("❌"))
                  badgeClass =
                    "text-red-400 font-medium bg-red-400/10 px-1 py-0.5 rounded";
                else if (log.includes("WARNING") || log.includes("⚠️"))
                  badgeClass =
                    "text-amber-300 font-medium bg-amber-400/10 px-1 py-0.5 rounded";
                else if (log.includes("✅") || log.includes("🎯"))
                  badgeClass =
                    "text-emerald-400 font-medium bg-emerald-400/10 px-1 py-0.5 rounded";
                else if (log.includes("info")) badgeClass = "text-indigo-300";

                return (
                  <div key={i} className="mb-1.5">
                    <span className={badgeClass}>{log}</span>
                  </div>
                );
              })}
              {logs.length === 0 && (
                <p className="text-slate-600 italic">
                  Waiting for incoming streams...
                </p>
              )}
            </div>
            {/* Terminal glow overlay */}
            <div className="absolute bottom-0 left-0 right-0 h-1/4 bg-gradient-to-t from-indigo-500/10 to-transparent pointer-events-none rounded-b-2xl"></div>
          </div>

          {/* PUBLICATIONS GRID */}
          <div className="bg-gradient-to-br from-slate-900/60 to-pink-900/10 border border-pink-500/10 rounded-2xl p-6 backdrop-blur-xl flex-1 shadow-2xl relative overflow-hidden">
            {/* Glow decor */}
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-pink-500/5 blur-[80px] -z-10 rounded-full"></div>

            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
              <Tv className="text-pink-400" size={20} />
              <h2 className="text-xl font-bold tracking-tight text-slate-100">
                Live Publication Ready
              </h2>
              <Button className="ml-auto text-slate-400 hover:text-white transition-colors">
                <RefreshCw size={18} />
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {videos.map((vid, i) => {
                const date = new Date(vid.published_at);
                const timeStr = `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;

                let platformColor =
                  "bg-red-500/10 text-red-500 border-red-500/30";
                if (vid.platform === "instagram")
                  platformColor =
                    "bg-pink-500/10 text-pink-400 border-pink-500/30";
                if (vid.platform === "facebook")
                  platformColor =
                    "bg-blue-500/10 text-blue-400 border-blue-500/30";
                if (vid.platform === "tiktok")
                  platformColor =
                    "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";

                return (
                  <div
                    key={i}
                    className="bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col gap-3 hover:border-pink-500/30 transition-colors group"
                  >
                    <div className="flex justify-between items-start">
                      <span
                        className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border ${platformColor}`}
                      >
                        {vid.platform}
                      </span>
                      <span className="text-xs font-mono text-slate-500">
                        {timeStr}
                      </span>
                    </div>
                    <h3 className="font-semibold text-sm text-slate-200 line-clamp-2 leading-relaxed">
                      {vid.topic_name}
                    </h3>
                    <div className="mt-auto pt-3 border-t border-white/5 line-clamp-1">
                      <Link
                        href={vid.video_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-pink-400 hover:text-pink-300 font-semibold group-hover:underline underline-offset-4 flex items-center gap-1"
                      >
                        Buka Folder GDrive &rarr;
                      </Link>
                    </div>
                  </div>
                );
              })}
              {videos.length === 0 && (
                <div className="col-span-full py-10 flex flex-col items-center gap-3 text-slate-500">
                  <RefreshCw className="animate-spin opacity-50" size={24} />
                  <p className="text-sm italic">
                    Scanning MongoDB for distributions...
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* Global CSS tweaks */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
      `,
        }}
      />
    </div>
  );
}
