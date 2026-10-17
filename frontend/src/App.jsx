
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

export default function App() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(event) {
    event.preventDefault();

    const text = message.trim();
    if (!text || loading) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: history.slice(-10),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The backend could not process this message."
        );
      }

      setResult(data);

      setHistory((previous) => [
        ...previous,
        { role: "user", content: text },
        { role: "assistant", content: data.response_markdown },
      ].slice(-10));

      setMessage("");
    } catch (err) {
      setError(err.message || "Could not connect to the backend.");
    } finally {
      setLoading(false);
    }
  }

  function resetConversation() {
    setHistory([]);
    setResult(null);
    setError("");
  }

  return (
    <main className="app">
      <header>
        <h1>AI Support Assistant</h1>
        <p>Ask a question and receive a context-aware AI response.</p>
      </header>

      <form onSubmit={sendMessage}>
        <label htmlFor="message">Your message</label>
        <textarea
          id="message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Example: My payment was deducted twice."
          maxLength={5000}
          required
        />

        <button type="submit" disabled={loading || !message.trim()}>
          {loading ? "Generating response..." : "Send message"}
        </button>

        <button type="button" onClick={resetConversation}>
          New conversation
        </button>
      </form>

      {error && <p role="alert" className="error">{error}</p>}

      {result && (
        <section className="response">
          <h2>AI Response</h2>

          <div className="markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {result.response_markdown}
            </ReactMarkdown>
          </div>

          <details>
            <summary>Intent analysis</summary>
            <p><strong>Intent:</strong> {result.intent}</p>
            <p><strong>Risk:</strong> {result.risk_profile}</p>
            <p><strong>Priority:</strong> {result.priority}</p>
            <p><strong>Summary:</strong> {result.summary}</p>
          </details>
        </section>
      )}
    </main>
  );
}
