"use client";

import "./globals.css";
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fi">
      <body className="app-root">
        <div className="app-shell">
          <header className="app-header">
            <div className="app-logo">Lapuan Kaupunki RAG</div>
            <div className="app-subtitle">
              Docling-pohjainen RAG-hakupalvelu, jossa Qdrant-vektorihaku ja Groq-LLM analysoivat
              Lapuan kaupungin pöytäkirjoja.
            </div>
          </header>
          <main className="app-main">{children}</main>
          <footer className="app-footer">© 2025 Lapua RAG • Tekoälypohjainen päätöshaku</footer>
        </div>
      </body>
    </html>
  );
}


