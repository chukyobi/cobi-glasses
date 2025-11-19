import { useRouter } from "expo-router";
import LoginScreen from "@/screens/LoginScreen"; 
import { useAuthStore } from "@/stores/useAuthStore";

export default function LoginRoute() {
  const router = useRouter();
  // Import signIn function
  const { signIn } = useAuthStore();

  const handleNavigateToSignUp = () => {
    // Navigate to the signup screen in the same (auth) stack
    router.push("./signup");
  };

  // 2. CORRECTED: The handler accepts credentials from the screen.
  const handleLoginAttempt = async (email: string, password: string) => {
    try {
      // 1. Call the store's signIn function, which handles API call, token saving, 
      //    and updating the global state (token, user).
      await signIn(email, password);

      // 2. If signIn is successful (no error thrown), the user is logged in.
      //    The RootLayout will handle the replacement to /(tabs) via useEffect, 
      //    but we perform an immediate replacement here for snappier navigation.
      router.replace("/(tabs)");

    } catch (error) {
      // Log the error and re-throw it so the UI (LoginScreen) can catch 
      // it and display an appropriate message to the user.
      console.error("Login attempt failed:", error);
      throw error;
    }
  };

  // 3. Pass the correct prop (`onLoginAttempt`) to the LoginScreen
  return (
    <LoginScreen
      onNavigateToSignUp={handleNavigateToSignUp}
      onLoginAttempt={handleLoginAttempt}
    />
  );
}
