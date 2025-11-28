
"use client";

import { useState, useRef, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Mic, Square, Brain, Radio, Volume2 } from "lucide-react";
import GlassesScene from "@/components/glasses-scene";
import TranscriptionDisplay from "@/components/transcription-display";
import ControlPanel from "@/components/control-panel";

const CONTROL_WEBSOCKET_URL = "ws://localhost:8000/control";

export default function Home() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [transcripts, setTranscripts] = useState<string[]>([]);
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [mode, setMode] = useState("local");
  const [isConnected, setIsConnected] = useState(false);

  // (Optional) keep env sound toast placeholder for future
  const [envSound, setEnvSound] = useState<{ label: string; confidence: number } | null>(null);

  const controlSocketRef = useRef<WebSocket | null>(null);

  const stopControlConnection = useCallback(() => {
    if (controlSocketRef.current) {
      if (controlSocketRef.current.readyState === WebSocket.OPEN) {
        controlSocketRef.current.send(JSON.stringify({ action: "stop" }));
      }
      controlSocketRef.current.close();
      controlSocketRef.current = null;
    }
    setIsConnected(false);
    setIsRecording(false);
  }, []);

  const startRecording = async () => {
    setTranscripts([]);
    setTranscript("");

    const ws = new WebSocket(CONTROL_WEBSOCKET_URL);
    controlSocketRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.partial) setTranscript(data.partial);
        if (data.final) {
          setTranscripts((prev) => [...prev, data.final]);
          setTranscript("");
        }
        // Optional: pass through environment events in the future
        if (data.type === "environment") {
          setEnvSound({ label: data.label, confidence: data.confidence });
          setTimeout(() => setEnvSound(null), 3000);
        }
      } catch (e) {
        console.error("Error processing message from bridge:", e);
      }
    };

    ws.addEventListener("open", () => {
      setIsConnected(true);
      console.log("Connected to Python Audio Bridge. Sending START command.");
      ws.send(JSON.stringify({ action: "start" })); // start mic capture in bridge
      setIsRecording(true);
    });

    ws.onclose = () => {
      setIsConnected(false);
      setIsRecording(false);
      console.log("Python Audio Bridge connection closed.");
    };

    ws.onerror = (err) => {
      console.error("WebSocket error", err);
      alert("Error: Python Audio Bridge (Port 8000) may not be running or reachable.");
      stopControlConnection();
    };
  };

  const toggleRecording = () => {
    if (isRecording) {
      controlSocketRef.current?.send(JSON.stringify({ action: "stop" }));
      stopControlConnection();
    } else {
      startRecording();
    }
  };

  const handleTranslateToggle = (enabled: boolean) => {
    setTranslateEnabled(enabled);
    // Route the translate toggle through the Bridge to Transcriber
    try {
      controlSocketRef.current?.send(JSON.stringify({
        action: "toggle_translate",
        enabled
      }));
    } catch (e) {
      console.warn("Translate toggle failed to send:", e);
    }
  };

  return (
    <main className="min-h-screen bg-linear-to-b from-slate-950 via-slate-900 to-black flex flex-col">
      {/* Optional: Environmental Sound Toast (hidden until classifier comes back) */}
      {envSound && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[60] animate-in slide-in-from-top-4 fade-in duration-300">
          <div className="flex items-center gap-3 px-6 py-3 bg-orange-500/10 border border-orange-500/40 backdrop-blur-xl rounded-full shadow-[0_0_30px_rgba(249,115,22,0.3)]">
            <Volume2 className="w-5 h-5 text-orange-400 animate-pulse" />
            <span className="text-orange-100 font-bold tracking-wide uppercase text-sm">
              {envSound.label}
            </span>
            <span className="text-xs text-orange-500 font-mono">
              {Math.round(envSound.confidence * 100)}%
            </span>
          </div>
        </div>
      )}

      <header className="border-b border-slate-800/50 bg-linear-to-r from-slate-950/80 to-slate-900/80 backdrop-blur-sm sticky top-0 z-50 py-4 lg:py-5">
        <div className="max-w-7xl mx-auto px-4 lg:px-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 lg:gap-3">
              <div className="w-9 lg:w-10 h-9 lg:h-10 rounded-lg bg-linear-to-br from-cyan-400 to-blue-400 flex items-center justify-center shrink-0">
                <Brain className="w-5 lg:w-6 h-5 lg:h-6 text-black" />
              </div>
              <div className="min-w-0">
                <h1 className="text-2xl lg:text-3xl font-display font-bold bg-linear-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent truncate">
                  COBI
                </h1>
                <p className="text-xs text-slate-400 tracking-widest font-medium hidden sm:block">
                  PERSONAL INTELLIGENCE
                </p>
              </div>
            </div>
            <Badge
              className={`flex items-center gap-2 px-2 lg:px-3 py-1 lg:py-2 text-xs font-semibold shrink-0 ${
                isConnected
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                  : "bg-red-500/20 text-red-400 border-red-500/30"
              }`}
              variant="outline"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? "bg-emerald-400" : "bg-red-400"
                } animate-pulse`}
              />
              <span className="hidden sm:inline">{isConnected ? "Connected" : "Offline"}</span>
              <span className="sm:hidden">{isConnected ? "On" : "Off"}</span>
            </Badge>
          </div>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 lg:gap-8 w-full max-w-7xl">
          <div className="hidden lg:flex lg:col-span-2 items-center justify-center">
            <div className="relative group w-full h-full min-h-[500px]">
              <div className="absolute inset-0 bg-linear-to-r from-cyan-500/20 to-blue-500/20 rounded-3xl blur-2xl group-hover:blur-3xl transition-all duration-500" />
              <GlassesScene isRecording={isRecording} />
            </div>
          </div>

          <div className="lg:col-span-3 flex items-center justify-center w-full">
            <Card className="w-full border-slate-700/50 bg-slate-900/40 backdrop-blur-2xl shadow-2xl rounded-2xl overflow-hidden">
              <div className="border-b border-slate-700/30 p-4 sm:p-6 lg:p-8 bg-linear-to-b from-slate-800/30 to-transparent">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Radio className="w-4 sm:w-5 h-4 sm:h-5 text-cyan-400 shrink-0" />
                    <h2 className="text-xl sm:text-2xl font-display font-bold text-white truncate">
                      Understand Intent
                    </h2>
                  </div>
                  <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                    Transform speech into human-aligned understanding
                  </p>
                </div>
              </div>

              <CardContent className="space-y-6 sm:space-y-8 py-6 sm:py-10 px-4 sm:px-8">
                <div className="flex flex-col items-center gap-4 sm:gap-6">
                  <div className="relative">
                    {isRecording && (
                      <>
                        <div
                          className="absolute inset-0 rounded-full bg-linear-to-r from-cyan-500 to-blue-500 animate-pulse"
                          style={{ boxShadow: "0 0 80px rgba(34, 211, 238, 0.6)" }}
                        />
                        <div
                          className="absolute inset-4 rounded-full border border-cyan-400/50"
                          style={{ animation: "pulse-ring 2s infinite" }}
                        />
                      </>
                    )}
                    <Button
                      onClick={toggleRecording}
                      size="lg"
                      className={`relative z-10 w-24 h-24 sm:w-28 sm:h-28 rounded-full flex items-center justify-center transition-all duration-300 font-bold text-lg ${
                        isRecording
                          ? "bg-linear-to-br from-cyan-500 to-blue-500 text-white"
                          : "bg-linear-to-br from-slate-700 to-slate-800 text-slate-100"
                      }`}
                    >
                      {isRecording ? (
                        <Square className="w-8 h-8 sm:w-10 sm:h-10 fill-white" />
                      ) : (
                        <Mic className="w-8 h-8 sm:w-10 sm:h-10" />
                      )}
                    </Button>
                  </div>
                  <div className="text-center">
                    <p className="text-xs sm:text-sm font-semibold text-slate-300 tracking-wide">
                      {isRecording ? "LISTENING..." : "TAP TO ACTIVATE"}
                    </p>
                  </div>
                </div>

                <TranscriptionDisplay finalTranscripts={transcripts} interimTranscript={transcript} />
              </CardContent>

              <div className="border-t border-slate-700/30 p-4 sm:p-6 lg:p-8 bg-linear-to-t from-slate-800/20 to-transparent">
                <ControlPanel
                  translateEnabled={translateEnabled}
                  setTranslateEnabled={handleTranslateToggle}
                  mode={mode}
                  setMode={setMode}
                />
              </div>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}
