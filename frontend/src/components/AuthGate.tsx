"use client";

import { useEffect, useState } from "react";

import { KanbanBoard } from "@/components/KanbanBoard";

const DEMO_USERNAME = "user";
const DEMO_PASSWORD = "password";
const AUTH_STORAGE_KEY = "pm-demo-auth";

export const AuthGate = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const savedSession = window.localStorage.getItem(AUTH_STORAGE_KEY);
    setIsAuthenticated(savedSession === "true");
  }, []);

  const handleLogin = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (username === DEMO_USERNAME && password === DEMO_PASSWORD) {
      setError("");
      window.localStorage.setItem(AUTH_STORAGE_KEY, "true");
      setIsAuthenticated(true);
      return;
    }

    setError("Invalid username or password");
  };

  const handleLogout = () => {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setIsAuthenticated(false);
    setUsername("");
    setPassword("");
    setError("");
  };

  if (isAuthenticated) {
    return (
      <div className="min-h-screen bg-[var(--surface)]">
        <div className="flex justify-end px-6 pt-6">
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-full bg-[var(--secondary-purple)] px-5 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow)] transition hover:opacity-90"
          >
            Log out
          </button>
        </div>
        <KanbanBoard username={DEMO_USERNAME} />
      </div>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
            Project board
          </p>
          <h1 className="mt-4 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            Sign in
          </h1>
        </div>

        <form className="space-y-5" onSubmit={handleLogin}>
          <div>
            <label htmlFor="username" className="mb-2 block text-sm font-semibold text-[var(--navy-dark)]">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2.5 text-base text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              autoComplete="username"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-semibold text-[var(--navy-dark)]">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2.5 text-base text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              autoComplete="current-password"
            />
          </div>

          {error ? (
            <p className="text-sm font-medium text-red-600" role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            className="w-full rounded-xl bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white shadow-[var(--shadow)] transition hover:opacity-90"
          >
            Log in
          </button>
        </form>
      </section>
    </main>
  );
};
