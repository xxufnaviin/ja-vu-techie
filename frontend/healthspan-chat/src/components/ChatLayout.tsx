import React, { useState } from 'react';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Menu, 
  MessageSquare, 
  Users, 
  Moon, 
  Sun, 
  Send, 
  ChevronLeft, 
  ChevronRight,
  Stethoscope
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import stethoscopeIcon from '@/assets/stethoscope-icon.png';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

const ChatLayout = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isPatientOpen, setIsPatientOpen] = useState(false);
  const { theme, setTheme } = useTheme();

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: "user",
      timestamp: new Date(),
    };
  
    const thinkingMessage: Message = {
      id: (Date.now() + 1).toString(),
      content: "Thinking...",
      sender: "ai",
      timestamp: new Date(),
    };
  
    // Add user + placeholder AI message
    setMessages((prev) => [...prev, userMessage, thinkingMessage]);
    setInputValue("");

    try {
      // Send user input to backend
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: inputValue }),
      });

      if (!res.ok) {
        throw new Error("Failed to fetch AI response");
      }

      const data = await res.json();

      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        content: data.response || "No response from AI.",
        sender: "ai",
        timestamp: new Date(),
      };

      // Replace "Thinking..." with AI response
      setMessages((prev) =>
        prev.map((m) => (m.id === thinkingMessage.id ? aiResponse : m))
      );

    } catch (error) {
      const errorMsg: Message = {
        id: (Date.now() + 2).toString(),
        content: "⚠️ Error contacting AI backend.",
        sender: "ai",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };


  const EmptyState = () => (
    <div className="flex flex-col items-center justify-center flex-1 px-8 py-12 text-center">
      <div className="medical-gradient w-24 h-24 rounded-full flex items-center justify-center mb-8 medical-shadow">
        <img src={stethoscopeIcon} alt="Stethoscope" className="w-12 h-12" />
      </div>
      <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-medical-primary to-medical-success bg-clip-text text-transparent">
        Hello, Doctor
      </h1>
      <p className="text-xl text-muted-foreground mb-2">
        How can I help you with patient care today?
      </p>
      <p className="text-sm text-muted-foreground max-w-md">
        Ask me about diagnoses, treatment plans, or pull patient records by saying "Pull the records of patient [name]"
      </p>
    </div>
  );

  const MessageBubble = ({ message }: { message: Message }) => (
    <div className={cn("flex mb-6", message.sender === "user" ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] px-4 py-3 text-sm leading-relaxed break-words overflow-hidden rounded-lg",
          message.sender === "user" ? "bg-primary text-primary-foreground ml-12" : "bg-muted mr-12 shadow-sm",
        )}
      >
        <div className="flex items-start gap-3">
          {message.sender === "ai" && (
            <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Stethoscope className="w-3 h-3 text-white" />
            </div>
          )}
          <div className="flex-1 min-w-0 overflow-wrap-anywhere">
            <div className="prose prose-sm max-w-none break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="break-words whitespace-pre-wrap">{children}</p>,
                  code: ({ children }) => <code className="break-all">{children}</code>,
                  pre: ({ children }) => (
                    <pre className="whitespace-pre-wrap break-words overflow-x-auto">{children}</pre>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          </div>
          {message.sender === "user" && (
            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
              <Users className="w-3 h-3 text-muted-foreground" />
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen w-full flex flex-col">
      {/* Header */}
      <header className="h-16 bg-background/80 backdrop-blur-md border-b border-border flex items-center justify-between px-6 sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <div className="medical-gradient w-10 h-10 rounded-full flex items-center justify-center">
            <img src={stethoscopeIcon} alt="MedChat AI" className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-medical-primary">MedChat AI</h1>
            <p className="text-xs text-muted-foreground">Intelligent Medical Assistant</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
            className="gap-2"
          >
            <MessageSquare className="w-4 h-4" />
            History
          </Button>
          
          {isPatientOpen && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsPatientOpen(false)}
              className="gap-2"
            >
              <Users className="w-4 h-4" />
              Patient Info
            </Button>
          )}
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4" />
            ) : (
              <Moon className="w-4 h-4" />
            )}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 relative">
        {/* Chat History Sidebar */}
        {isHistoryOpen && (
          <aside className="w-80 bg-card border-r border-border animate-slide-in-left flex flex-col">
            <div className="p-4 border-b border-border">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">Chat History</h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsHistoryOpen(false)}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
              </div>
              <Button size="sm" className="w-full medical-gradient text-white">
                New Chat
              </Button>
            </div>
            
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg bg-muted/50 hover:bg-muted cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <MessageSquare className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm font-medium">Patient Consultation {i}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-1">2 hours ago • 8 messages</p>
                    <p className="text-xs text-muted-foreground truncate">
                      Discussed diabetes management...
                    </p>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </aside>
        )}

        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col">
          <ScrollArea className="flex-1">
            <div className="min-h-full flex flex-col">
              {messages.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="flex-1 p-6 pb-32">
                  {messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Chat Input */}
          <div className="sticky bottom-0 bg-background/80 backdrop-blur-md border-t border-border p-4">
            <div className="max-w-4xl mx-auto">
              <div className="relative">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder={
                    messages.length === 0 
                      ? "Ask me anything about patient care..." 
                      : "Type your message..."
                  }
                  className="pr-12 py-6 text-base rounded-xl bg-chat-input-bg border-border focus:ring-2 focus:ring-medical-primary/20 focus:border-medical-primary"
                />
                <Button
                  size="sm"
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim()}
                  className={cn(
                    "absolute right-2 top-2 bottom-2 w-10 h-10 rounded-lg transition-all duration-200",
                    inputValue.trim() 
                      ? "medical-gradient text-white medical-shadow" 
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </main>

        {/* Patient Info Sidebar */}
        {isPatientOpen && (
          <aside className="w-80 bg-card border-l border-border animate-slide-in-right flex flex-col">
            <div className="p-4 border-b border-border">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">Patient Information</h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsPatientOpen(false)}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
            
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {/* Patient Card */}
                <div className="p-4 rounded-lg bg-muted/30 border-l-4 border-medical-primary">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-12 h-12 rounded-full medical-gradient-light flex items-center justify-center">
                      <span className="text-medical-primary font-semibold">AH</span>
                    </div>
                    <div>
                      <h3 className="font-semibold">Ahmad Hassan</h3>
                      <p className="text-sm text-muted-foreground">45 years old</p>
                    </div>
                  </div>
                  
                  {/* Diagnoses */}
                  <div className="mb-3">
                    <h4 className="text-sm font-medium mb-2">Diagnoses</h4>
                    <div className="flex flex-wrap gap-1">
                      <span className="px-2 py-1 text-xs rounded-full bg-medical-error/10 text-medical-error border border-medical-error/20">
                        Type 2 Diabetes
                      </span>
                      <span className="px-2 py-1 text-xs rounded-full bg-medical-warning/10 text-medical-warning border border-medical-warning/20">
                        Hypertension
                      </span>
                    </div>
                  </div>
                  
                  {/* Medications */}
                  <div>
                    <h4 className="text-sm font-medium mb-2">Medications</h4>
                    <div className="space-y-2">
                      <div className="text-xs bg-muted/50 p-2 rounded">
                        <span className="font-medium">Metformin</span>
                        <span className="text-muted-foreground ml-1">500mg BID</span>
                      </div>
                      <div className="text-xs bg-muted/50 p-2 rounded">
                        <span className="font-medium">Lisinopril</span>
                        <span className="text-muted-foreground ml-1">10mg Daily</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </aside>
        )}
      </div>
    </div>
  );
};

export default ChatLayout;