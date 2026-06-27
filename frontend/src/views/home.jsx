import React from "react"
import ChatbotPanel from "../components/home/ChatbotPanel"
import CalendarPanel from "../components/home/calendar"
import ValuesPanel from "../components/home/values"
import GoalsPanel from "../components/home/GoalsPanel"
import { valueWeights } from "../components/home/data"
import "../components/home/home-layout.css"

export default function Home() {
  return (
    <div className="home-page">
      <div className="home-shell">
        <ChatbotPanel />
        <CalendarPanel />
        <div className="home-right-column">
          <ValuesPanel valueWeights={valueWeights} />
          <GoalsPanel />
        </div>
      </div>
    </div>
  )
}
