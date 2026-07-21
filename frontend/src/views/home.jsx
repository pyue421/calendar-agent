import React from "react"
import SessionProvider, { useSession } from "../services/SessionContext"
import { DEFAULT_VALUE_WEIGHTS } from "../services/defaultValueWeights"
import ChatbotPanel from "../components/home/ChatbotPanel"
import CalendarPanel from "../components/home/calendar"
import ValuesPanel from "../components/home/values"
import "../components/home/home-layout.css"

function HomeContent() {
  const { valueWeights, previewValueWeights, previewConfirmed } = useSession()

  // Fallback to default weights if none from backend yet
  const weights =
    valueWeights && valueWeights.length > 0 ? valueWeights : DEFAULT_VALUE_WEIGHTS

  return (
    <div className="home-page">
      <div className="home-shell">
        <ChatbotPanel />
        <div className="home-right-column">
          <ValuesPanel
            valueWeights={weights}
            previewWeights={previewValueWeights}
            previewConfirmed={previewConfirmed}
          />
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
