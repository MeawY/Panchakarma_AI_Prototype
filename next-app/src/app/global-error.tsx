"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ja">
      <body style={{ margin: 0, padding: "2rem", fontFamily: "sans-serif", background: "#fbfaf7" }}>
        <div style={{ maxWidth: "600px", margin: "0 auto" }}>
          <h1 style={{ color: "#c00" }}>アプリのエラー</h1>
          <p>{error.message}</p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "0.5rem 1rem",
              background: "#2f2f2f",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            再試行
          </button>
        </div>
      </body>
    </html>
  );
}
