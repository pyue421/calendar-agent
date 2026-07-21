import React from "react"
import SessionProvider, { useSession } from "../services/SessionContext"
import ChatbotPanel from "../components/home/ChatbotPanel"
import CalendarPanel from "../components/home/calendar"
import ValuesPanel from "../components/home/values"
import GoalsPanel from "../components/home/GoalsPanel"
import ValuePreviewPanel from "../components/home/ValuePreviewPanel"
import "../components/home/home-layout.css"

function HomeContent() {
  const { valueWeights } = useSession()

  // Fallback to default weights if none from backend yet
  const weights =
    valueWeights && valueWeights.length > 0
      ? valueWeights
      : [
          {
            label: "Value 1",
            weight: 20,
            tone: "green",
            evidence: [{ id: "d1", text: "Waiting on your first conversation", round: 0 }],
            calendarEvents: [{ id: "d1c", text: "Waiting on your first calendar action", round: 0 }],
          },
          {
            label: "Value 2",
            weight: 20,
            tone: "rose",
            evidence: [{ id: "y1", text: "Keep chatting to surface this value", round: 0 }],
            calendarEvents: [{ id: "y1c", text: "Accept or decline events to surface this value", round: 0 }],
          },
          {
            label: "Value 3",
            weight: 20,
            tone: "amber",
            evidence: [{ id: "v1", text: "Keep chatting to surface this value", round: 0 }],
            calendarEvents: [{ id: "v1c", text: "Accept or decline events to surface this value", round: 0 }],
          },
          {
            label: "Value 4",
            weight: 20,
            tone: "cyan",
            evidence: [{ id: "t1", text: "Keep chatting to surface this value", round: 0 }],
            calendarEvents: [{ id: "t1c", text: "Accept or decline events to surface this value", round: 0 }],
          },
          {
            label: "Value 5",
            weight: 20,
            tone: "violet",
            evidence: [{ id: "a1", text: "Keep chatting to surface this value", round: 0 }],
            calendarEvents: [{ id: "a1c", text: "Accept or decline events to surface this value", round: 0 }],
          },
        ]

  return (
    <div className="home-page">
      <div className="home-shell">
        <ChatbotPanel />
        <CalendarPanel />
        <div className="home-right-column">
          <ValuesPanel valueWeights={weights} />
          <ValuePreviewPanel />
          <GoalsPanel />
        </div>
      </div>
    </div>
  )
}

export default function Home() {
  return (
    <SessionProvider>
      <HomeContent />
    </SessionProvider>
  )
}
