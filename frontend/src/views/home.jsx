import React from "react"
import SessionProvider from "../services/SessionContext"
import ChatbotPanel from "../components/home/ChatbotPanel"
import CalendarPanel from "../components/home/calendar"
import ValuesPanel from "../components/home/values"
import "../components/home/home-layout.css"

function HomeContent() {
  return (
    <div className="home-page">
      <div className="home-shell">
        <ChatbotPanel />
        <div className="home-right-column">
          <ValuesPanel />
        </div>
        <CalendarPanel />
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
