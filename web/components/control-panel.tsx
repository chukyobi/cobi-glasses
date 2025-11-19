"use client"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Languages, Cpu } from "lucide-react"

export default function ControlPanel({
  translateEnabled,
  setTranslateEnabled,
  mode,
  setMode,
}: {
  translateEnabled: boolean
  setTranslateEnabled: (value: boolean) => void
  mode: string
  setMode: (value: string) => void
}) {
  return (
    <div className="w-full flex flex-col gap-4 sm:gap-6">
      {/* Translate Toggle */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 sm:py-3 rounded-lg bg-slate-800/30 border border-slate-700/50 hover:border-slate-600/50 transition-colors">
        <div className="flex items-center gap-2 sm:gap-3">
          <Languages className="w-4 h-4 text-cyan-400 shrink-0" />
          <Label htmlFor="translate" className="text-slate-200 font-medium text-xs sm:text-sm cursor-pointer">
            Translation
          </Label>
        </div>
        <Switch
          id="translate"
          checked={translateEnabled}
          onCheckedChange={setTranslateEnabled}
          className="data-[state=checked]:bg-cyan-500"
        />
      </div>

      {/* Mode Selector */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-400 shrink-0" />
          <Label className="text-slate-200 font-medium text-xs sm:text-sm">Processing Mode</Label>
        </div>
        <div className="flex gap-2 bg-slate-800/30 rounded-lg p-1.5 border border-slate-700/50">
          {["Local", "Cloud"].map((modeOption) => (
            <button
              key={modeOption}
              onClick={() => setMode(modeOption.toLowerCase())}
              className={`flex-1 px-3 sm:px-4 py-2 rounded text-xs font-semibold transition-all ${
                mode === modeOption.toLowerCase()
                  ? "bg-linear-to-br from-cyan-500 to-blue-500 text-white shadow-lg shadow-cyan-500/50"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/30"
              }`}
            >
              {modeOption}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
