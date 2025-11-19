"use client"

import { Canvas } from "@react-three/fiber"
import { PerspectiveCamera, Environment, OrbitControls } from "@react-three/drei"
import GlassesModel from "./glasses-model"

export default function GlassesScene({ isRecording }: { isRecording: boolean }) {
  return (
    <div className="w-full h-screen rounded-2xl overflow-hidden border border-slate-700/50 bg-gradient-to-b from-slate-900/40 to-slate-950/40 backdrop-blur-sm">
      <Canvas>
        <PerspectiveCamera makeDefault position={[0, 0, 6]} />
        <Environment preset="night" />
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={1.5} color="#06b6d4" />
        <pointLight position={[-10, -10, 5]} intensity={0.8} color="#3b82f6" />
        <pointLight position={[0, 0, 15]} intensity={1} color="#0891b2" />
        <GlassesModel isRecording={isRecording} />
        <OrbitControls enableZoom={true} autoRotate autoRotateSpeed={isRecording ? 5 : 1.5} enablePan={false} />
      </Canvas>
    </div>
  )
}
