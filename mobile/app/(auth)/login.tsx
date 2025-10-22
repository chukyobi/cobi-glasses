import { useRouter } from "expo-router"
import LoginScreen from "@/screens/LoginScreen"
import { useAuthStore } from "@/stores/useAuthStore" 
import {User} from "@/interfaces/User"



export default function LoginRoute() {
  const router = useRouter()
  // Import signIn function
  const { signIn } = useAuthStore() 

  const handleNavigateToSignUp = () => {
    router.push("./signup")
  }

  // 2. Type the parameters to remove implicit 'any' errors
  const handleLoginSuccess = async (user: User, token: string) => {
    // 1. Save session data
    await signIn(user, token) 

    // 2. Check the user's onboarding status (based on server data)
    if (user.isOnboarded) {
        router.replace("/(tabs)")
    } 
  }

  // 3. Pass the correctly typed prop to the updated LoginScreen
  return <LoginScreen 
    onNavigateToSignUp={handleNavigateToSignUp} 
    onLoginSuccess={handleLoginSuccess} 
  />
}
