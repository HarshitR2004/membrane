export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("membrane_api_key");
}

export function setApiKey(key: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("membrane_api_key", key);
  }
}

export function getWallet(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("membrane_wallet");
}

export function setWallet(wallet: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("membrane_wallet", wallet);
  }
}

export function clearAuth() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("membrane_api_key");
    localStorage.removeItem("membrane_wallet");
  }
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = getApiKey();
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");

  const cleanBase = API_BASE.replace(/\/+$/, '');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  const res = await fetch(`${cleanBase}${cleanEndpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${res.status}`);
  }

  return res.json();
}
