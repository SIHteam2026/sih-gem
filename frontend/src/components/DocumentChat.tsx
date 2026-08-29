"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Sparkles,
  User,
  Bot,
  MessageSquare,
  Loader2,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { askProcurementQuestion } from "@/services/api";

interface Message {
  role: "user" | "assistant" | "error";
  content: string;
  timestamp?: Date;
}

interface DocumentChatProps {
  documentContext?: string;
  placeholder?: string;
  title?: string;
}

export default function DocumentChat({
  documentContext = "",
  placeholder = "Ask a question about this document or procurement requirement...",
  title = "AI Procurement Assistant",
}: DocumentChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm your AI Procurement Assistant. Ask me anything about the tender clauses, eligibility requirements, or compliance rules — I'll analyse the provided document context to give you a precise answer.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to the latest message whenever messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await askProcurementQuestion(trimmed, documentContext);

      const answer =
        response?.answer ||
        response?.response ||
        response?.message ||
        response?.text ||
        response?.content ||
        (typeof response === "string" ? response : JSON.stringify(response, null, 2));

      const assistantMessage: Message = {
        role: "assistant",
        content: answer,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          content: err?.message || "An error occurred while contacting the procurement assistant.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
      // Re-focus the input
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift), allow Shift+Enter for newlines
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "Chat cleared. Feel free to ask a new question about the tender or bidder documents.",
        timestamp: new Date(),
      },
    ]);
    setInput("");
    inputRef.current?.focus();
  };

  const formatTimestamp = (date?: Date): string => {
    if (!date) return "";
    return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex flex-col bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden font-sans h-[600px]">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-gradient-to-r from-indigo-50 via-white to-indigo-50 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center shadow-sm flex-shrink-0">
            <Sparkles className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <h3 className="font-extrabold text-gray-900 text-sm leading-tight">{title}</h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[11px] text-gray-500">Context-aware · GeM Procurement Compliance</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleClearChat}
          title="Clear chat history"
          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Context Badge — only shown if documentContext was passed */}
      {documentContext && documentContext.length > 0 && (
        <div className="px-5 py-2 bg-indigo-50/60 border-b border-indigo-100 flex items-center gap-2 flex-shrink-0">
          <MessageSquare className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
          <p className="text-[11px] text-indigo-700 font-medium truncate">
            <span className="font-bold">Document context loaded:</span>{" "}
            {documentContext.slice(0, 120)}
            {documentContext.length > 120 ? "…" : ""}
          </p>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 scroll-smooth">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => {
            const isUser = msg.role === "user";
            const isError = msg.role === "error";

            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.2 }}
                className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${
                    isUser
                      ? "bg-indigo-600"
                      : isError
                      ? "bg-red-100"
                      : "bg-gray-200"
                  }`}
                >
                  {isUser ? (
                    <User className="w-3.5 h-3.5 text-white" />
                  ) : isError ? (
                    <AlertCircle className="w-3.5 h-3.5 text-red-600" />
                  ) : (
                    <Bot className="w-3.5 h-3.5 text-gray-600" />
                  )}
                </div>

                {/* Bubble */}
                <div className={`max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                  <div
                    className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap shadow-2xs ${
                      isUser
                        ? "bg-indigo-600 text-white rounded-br-sm"
                        : isError
                        ? "bg-red-50 text-red-700 border border-red-200 rounded-bl-sm"
                        : "bg-gray-100 text-gray-800 rounded-bl-sm"
                    }`}
                  >
                    {msg.content}
                  </div>
                  <span className="text-[10px] text-gray-400 mt-1 px-1">
                    {formatTimestamp(msg.timestamp)}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Loading Indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-end gap-2.5"
          >
            <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0 shadow-sm">
              <Bot className="w-3.5 h-3.5 text-gray-600" />
            </div>
            <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-sm shadow-2xs">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </motion.div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Row */}
      <div className="flex-shrink-0 border-t border-gray-200 px-4 py-3 bg-white">
        <div className="flex items-end gap-2 bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-200 transition-all">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading}
            className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none disabled:opacity-60 max-h-32 leading-relaxed"
            style={{ overflow: "hidden" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 128) + "px";
            }}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading}
            className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all ${
              !input.trim() || isLoading
                ? "bg-gray-300 cursor-not-allowed text-gray-500"
                : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm cursor-pointer"
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        <p className="text-[10px] text-gray-400 mt-1.5 px-1">
          Press <kbd className="font-mono bg-gray-100 border border-gray-200 rounded px-1">Enter</kbd> to send ·{" "}
          <kbd className="font-mono bg-gray-100 border border-gray-200 rounded px-1">Shift+Enter</kbd> for a new line
        </p>
      </div>
    </div>
  );
}
