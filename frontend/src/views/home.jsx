import React from "react"
import SessionProvider, { useSession } from "../services/SessionContext"
import ChatbotPanel from "../components/home/ChatbotPanel"
import CalendarPanel from "../components/home/calendar"
import ValuesPanel from "../components/home/values"
import "../components/home/home-layout.css"

function HomeContent() {
  const { valueWeights } = useSession()

  const weights = valueWeights || []

  return (
    <div className="home-page">
      <div className="home-shell">
        <ChatbotPanel />
        <CalendarPanel />
        <div className="home-right-column">
          <ValuesPanel valueWeights={weights} />
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
