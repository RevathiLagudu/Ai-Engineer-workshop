import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

export default function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(text = message) {
    if (!text.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/analyze",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            history: [],
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The request failed."
        );
      }

      setAnswer(data.response_markdown || "No response was returned.");
      setMessage("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">✦</div>
          <div>
            <h2>AI Assistant</h2>
            <p>Get help with your queries</p>
          </div>
        </div>

        <button className="new-chat" onClick={() => {
          setAnswer("");
          setError("");
          setMessage("");
        }}>
          ＋ New Chat
        </button>

        <div className="sidebar-section">
          <h3>Suggested Prompts</h3>
          {[
            "My payment was deducted twice. What should I do?",
            "How can I reset my password?",
            "I want to check my order status.",
            "What are your refund policies?",
            "How do I contact customer support?",
          ].map((prompt) => (
            <button
              className="suggestion"
              key={prompt}
              onClick={() => sendMessage(prompt)}
              disabled={loading}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="backend-status">
          <span className="status-dot" />
          <div>
            <strong>FastAPI + Groq</strong>
            <p>AI Support Assistant</p>
          </div>
        </div>
      </aside>

      <main className="chat-panel">
        <header className="chat-header">
          <h2>New Chat</h2>
        </header>

        <section className="chat-messages">
          {!answer && !loading && (
            <div className="welcome">
              <div className="welcome-icon">✦</div>
              <h1>How can I help you?</h1>
              <p>Ask a question to get started.</p>
            </div>
          )}

          {loading && <p>AI is thinking...</p>}

          {answer && (
            <div className="assistant-message">
              <div className="assistant-label">✦ AI Assistant</div>
              <div className="assistant-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {answer}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </section>

        {error && <div className="error-message">{error}</div>}

        <form
          className="chat-form"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage();
          }}
        >
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Type your message..."
            rows={1}
            required
          />
          <button type="submit" disabled={loading}>
            ➤
          </button>
        </form>

        <p className="disclaimer">
          AI-generated responses may not always be accurate.
        </p>
      </main>
    </div>
  );
}