//app/(auth)/signup.tsx
"use client"

import { useRouter } from "expo-router"
import SignUpScreen from "@/screens/SignUpScreen"

export default function SignUpRoute() {
  const router = useRouter()

  const handleNavigateToLogin = () => {
    router.back()
  }

  const handleSkip = () => {
    router.replace("/(tabs)")
  }

  const handleSignUp = () => {
    router.replace("/(tabs)")
  }

  return <SignUpScreen onNavigateToLogin={handleNavigateToLogin} onSkip={handleSkip} onSignUp={handleSignUp} />
}
