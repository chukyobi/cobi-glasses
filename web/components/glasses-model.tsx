"use client"

import { useRef } from "react"
import { useFrame } from "@react-three/fiber"
import type * as THREE from "three"

export default function GlassesModel({ isRecording }: { isRecording: boolean }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame(({ clock }) => {
    if (groupRef.current) {
      // Floating motion on Y axis
      groupRef.current.position.y = Math.sin(clock.getElapsedTime() * 0.8) * 0.5

      if (isRecording) {
        groupRef.current.rotation.z += 0.005
      }
    }
  })

  return (
    <group ref={groupRef} scale={2}>
      {/* Left lens */}
      <mesh position={[-1.2, 0, 0]}>
        <sphereGeometry args={[0.6, 64, 64]} />
        <meshStandardMaterial
          color="#0891b2"
          metalness={0.95}
          roughness={0.05}
          emissive={isRecording ? "#06b6d4" : "#000000"}
          emissiveIntensity={isRecording ? 1.2 : 0.3}
          envMapIntensity={1.5}
        />
      </mesh>

      {/* Right lens */}
      <mesh position={[1.2, 0, 0]}>
        <sphereGeometry args={[0.6, 64, 64]} />
        <meshStandardMaterial
          color="#0891b2"
          metalness={0.95}
          roughness={0.05}
          emissive={isRecording ? "#06b6d4" : "#000000"}
          emissiveIntensity={isRecording ? 1.2 : 0.3}
          envMapIntensity={1.5}
        />
      </mesh>

      {/* Bridge - more refined */}
      <mesh position={[0, 0.15, 0]}>
        <boxGeometry args={[0.5, 0.2, 0.2]} />
        <meshStandardMaterial
          color="#1e293b"
          metalness={0.8}
          roughness={0.2}
          emissive={isRecording ? "#0ea5e9" : "#000000"}
          emissiveIntensity={isRecording ? 0.4 : 0}
        />
      </mesh>

      {/* Left arm */}
      <mesh position={[-1.8, 0, 0]}>
        <boxGeometry args={[0.8, 0.15, 0.15]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Right arm */}
      <mesh position={[1.8, 0, 0]}>
        <boxGeometry args={[0.8, 0.15, 0.15]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.3} />
      </mesh>

      {isRecording && (
        <>
          {/* Left lens glow */}
          <mesh position={[-1.2, 0, 0.8]}>
            <sphereGeometry args={[1.8, 32, 32]} />
            <meshBasicMaterial color="#06b6d4" wireframe transparent opacity={0.15} />
          </mesh>
          {/* Right lens glow */}
          <mesh position={[1.2, 0, 0.8]}>
            <sphereGeometry args={[1.8, 32, 32]} />
            <meshBasicMaterial color="#3b82f6" wireframe transparent opacity={0.15} />
          </mesh>
          {/* Overall aura */}
          <mesh position={[0, 0, 0]}>
            <sphereGeometry args={[3, 32, 32]} />
            <meshBasicMaterial color="#0891b2" wireframe transparent opacity={0.08} />
          </mesh>
        </>
      )}
    </group>
  )
}
