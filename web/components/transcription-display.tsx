"use client"

import { CheckCircle2, Volume2 } from "lucide-react"

export default function TranscriptionDisplay({
  finalTranscripts,
  interimTranscript,
}: {
  finalTranscripts: string[]
  interimTranscript: string
}) {
  return (
    <div className="min-h-64 sm:min-h-80 border border-slate-700/50 rounded-xl bg-linear-to-br from-slate-800/30 to-slate-900/30 p-4 sm:p-6 overflow-y-auto backdrop-blur-sm space-y-3 shadow-lg">
      {finalTranscripts.length === 0 && !interimTranscript && (
        <div className="h-full flex items-center justify-center min-h-48 sm:min-h-64">
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-linear-to-br from-cyan-500/20 to-blue-500/20 mx-auto mb-3 flex items-center justify-center animate-glow">
              <Volume2 className="w-6 h-6 text-cyan-400" />
            </div>
            <p className="text-slate-500 text-sm font-medium">Awaiting voice input...</p>
          </div>
        </div>
      )}

      {finalTranscripts.map((text, idx) => (
        <div
          key={idx}
          className="group p-3 sm:p-4 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-cyan-500/30 transition-all hover:bg-slate-800/50"
        >
          <div className="flex items-start gap-2 sm:gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-slate-100 font-medium text-xs sm:text-sm leading-relaxed wrap-break-word">{text}</p>
              <p className="text-xs text-slate-500 mt-1 sm:mt-2">Understood and processed</p>
            </div>
          </div>
        </div>
      ))}

      {interimTranscript && (
        <div className="p-3 sm:p-4 rounded-lg bg-cyan-500/10 border border-cyan-500/30 animate-pulse">
          <p className="text-cyan-300 italic text-xs sm:text-sm leading-relaxed font-medium flex items-center gap-2 wrap-break-word">
            <Volume2 className="w-3 h-3 sm:w-4 sm:h-4 text-cyan-400 shrink-0" />
            {interimTranscript}
          </p>
        </div>
      )}

      {(finalTranscripts.length > 0 || interimTranscript) && (
        <div className="flex items-center gap-2 pt-3 sm:pt-4">
          <div className="flex-1 h-0.5 bg-gr-to-r from-cyan-500 via-blue-500 to-transparent rounded-full"></div>
          <span className="text-xs text-cyan-400 font-mono font-semibold whitespace-nowrap">LIVE</span>
        </div>
      )}
    </div>
  )
}
