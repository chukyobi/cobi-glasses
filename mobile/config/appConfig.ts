// ...

/**
 * Configuration for the application, pulling values from environment variables
 * with fallback defaults for local development.
 */
export const AppConfig = {
    // Reads the variable defined in your .env file
    API_URL: process.env.EXPO_PUBLIC_API_URL || 'https://cb9f3396e16d.ngrok-free.app/api/users', 
  
    // Reads the variable defined in your .env file
    TOKEN_KEY: process.env.EXPO_PUBLIC_TOKEN_KEY || 'userToken', 
  };
  