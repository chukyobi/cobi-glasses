"use client"

import { useEffect } from "react"
import { useRouter } from "expo-router"
import SplashScreen from "@/screens/SplashScreen"

export default function SplashScreenRoute() {
  const router = useRouter()

  useEffect(() => {
    const timer = setTimeout(() => {
      router.replace("/onboarding")
    }, 3000)

    return () => clearTimeout(timer)
  }, [router])

  return <SplashScreen />
}
