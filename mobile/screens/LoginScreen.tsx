import { useState } from "react"
import {
  View,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native"
import { LinearGradient } from "expo-linear-gradient"
import { User } from "@/interfaces/User"

// Update the props interface to match what LoginRoute is passing
interface LoginScreenProps {
  onNavigateToSignUp: () => void
  // Changed from onLogin/onSkip to the unified success handler
  onLoginSuccess: (user: User, token: string) => Promise<void>
}

export default function LoginScreen({
  onNavigateToSignUp,
  onLoginSuccess, 
}: LoginScreenProps) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)

  const handleLogin = () => {
    console.log("Login attempt:", { email, password })

    // --- MOCK API CALL SUCCESS ---
    // In a real app, this is where you'd call your API.
    // The response would give you the token and the user object, including isOnboarded status.
    
    // MOCK DATA: Simulating server response. If email contains 'new', we treat them as a new user (isOnboarded=false).
    // Use an email like "old@user.com" to go straight to tabs.
    // Use an email like "new@user.com" to go to onboarding.
    const mockUser: User = {
        id: 'user-id-' + Math.random().toString(36).substring(7),
        name: 'Mock User',
        email: email, 
        isOnboarded: !email.toLowerCase().includes("new"), // If email contains 'new', isOnboarded=false
    };
    const mockToken = 'mock-jwt-token-for-' + mockUser.id;

    // Call the success handler in the router component to handle saving and navigation
    onLoginSuccess(mockUser, mockToken);
  }

  return (
    <LinearGradient
      colors={["#0f172a", "#1e293b", "#0f172a"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.keyboardView}>
        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {/* Header */}
          <View style={styles.header}>
            {/* The "Skip" button has been visually removed as onboarding is mandatory */}
            {/* We keep the style container just in case it affects layout, but empty */}
            <View style={styles.skipButtonTop} />
            <Text style={styles.logo}>Cobi</Text>
            <Text style={styles.subtitle}>Welcome Back</Text>
          </View>

          {/* Form */}
          <View style={styles.form}>
            {/* Email Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Email</Text>
              <TextInput
                style={styles.input}
                placeholder="you@example.com (try 'new@user.com' or 'old@user.com')"
                placeholderTextColor="#64748b"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>

            {/* Password Input */}
            <View style={styles.inputGroup}>
              <View style={styles.passwordHeader}>
                <Text style={styles.label}>Password</Text>
                <TouchableOpacity>
                  <Text style={styles.forgotPassword}>Forgot?</Text>
                </TouchableOpacity>
              </View>
              <View style={styles.passwordInputContainer}>
                <TextInput
                  style={styles.passwordInput}
                  placeholder="••••••••"
                  placeholderTextColor="#64748b"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                />
                <TouchableOpacity onPress={() => setShowPassword(!showPassword)}>
                  <Text style={styles.eyeIcon}>{showPassword ? "👁️" : "👁️‍🗨️"}</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Login Button */}
            <TouchableOpacity style={styles.loginButton} onPress={handleLogin}>
              <Text style={styles.loginButtonText}>Log In</Text>
            </TouchableOpacity>

            {/* Divider */}
            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or continue with</Text>
              <View style={styles.dividerLine} />
            </View>

            {/* Social Login */}
            <View style={styles.socialContainer}>
              <TouchableOpacity style={styles.socialButton}>
                <Text style={styles.socialIcon}>🍎</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.socialButton}>
                <Text style={styles.socialIcon}>🔍</Text>
              </TouchableOpacity>
            </View>

            {/* Sign Up Link */}
            <View style={styles.signUpContainer}>
              <Text style={styles.signUpText}>Dont have an account? </Text>
              <TouchableOpacity onPress={onNavigateToSignUp}>
                <Text style={styles.signUpLink}>Sign Up</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingVertical: 40,
    justifyContent: "center",
  },
  header: {
    alignItems: "center",
    marginBottom: 40,
    position: "relative",
  },
  skipButtonTop: { // Now just a placeholder to maintain alignment
    position: "absolute",
    top: 0,
    right: 0,
    width: 60, // Give it a fixed size for alignment
    height: 24, // Matches font size
  },
  logo: {
    fontSize: 48,
    fontWeight: "700",
    color: "#3b82f6",
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 18,
    color: "#cbd5e1",
    marginTop: 12,
  },
  form: {
    gap: 20,
  },
  inputGroup: {
    gap: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#e2e8f0",
  },
  input: {
    backgroundColor: "#1e293b",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: "#ffffff",
    fontSize: 16,
  },
  passwordHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  passwordInputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1e293b",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    paddingHorizontal: 16,
  },
  passwordInput: {
    flex: 1,
    paddingVertical: 12,
    color: "#ffffff",
    fontSize: 16,
  },
  eyeIcon: {
    fontSize: 18,
  },
  forgotPassword: {
    fontSize: 14,
    color: "#3b82f6",
    fontWeight: "500",
  },
  loginButton: {
    backgroundColor: "#3b82f6",
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  loginButtonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 20,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#334155",
  },
  dividerText: {
    marginHorizontal: 12,
    color: "#64748b",
    fontSize: 14,
  },
  socialContainer: {
    flexDirection: "row",
    gap: 12,
    justifyContent: "center",
  },
  socialButton: {
    width: 56,
    height: 56,
    borderRadius: 8,
    backgroundColor: "#1e293b",
    borderWidth: 1,
    borderColor: "#334155",
    justifyContent: "center",
    alignItems: "center",
  },
  socialIcon: {
    fontSize: 24,
  },
  signUpContainer: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: 20,
  },
  signUpText: {
    color: "#cbd5e1",
    fontSize: 14,
  },
  signUpLink: {
    color: "#3b82f6",
    fontSize: 14,
    fontWeight: "600",
  },
})
