"use client"

import { useRouter } from "expo-router"
import LoginScreen from "@/screens/LoginScreen"

export default function LoginRoute() {
  const router = useRouter()

  const handleNavigateToSignUp = () => {
    router.push("./signup")
  }

  const handleSkip = () => {
    router.replace("/(tabs)")
  }

  const handleLogin = () => {
    router.replace("/(tabs)")
  }

  return <LoginScreen onNavigateToSignUp={handleNavigateToSignUp} onSkip={handleSkip} onLogin={handleLogin} />
}
