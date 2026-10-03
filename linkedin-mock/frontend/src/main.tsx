import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthError, ME_KEY } from "./api";
import App from "./App";
import "./styles.css";

// Any 401 means the session is gone: clear the current user so the app shows the login page.
const onError = (error: Error) => {
  if (error instanceof AuthError) queryClient.setQueryData(ME_KEY, null);
};

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError }),
  mutationCache: new MutationCache({ onError }),
  defaultOptions: {
    queries: { staleTime: 10_000, retry: (count, error) => !(error instanceof AuthError) && count < 1 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
