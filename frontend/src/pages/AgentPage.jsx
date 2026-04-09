import { useEffect, useRef, useCallback, useState } from 'react'
import { useVoice } from '../hooks/useVoice'
import { generateBookingPDF } from '../components/cards/BookingCard'
import SharedHeader from '../components/SharedHeader'
import ChatFeed from '../components/ChatFeed'
import ChatInput from '../components/ChatInput'

export default function AgentPage({ member, onSwitchToStore, onSwitchToAgent, onSwitchToDashboard, initialVehicle, chatState }) {
  const {
    sessionId, messages, stage, isTyping,
    lastBotText, lastBookingCard, sendMessage, sendImage, sendFeedback, goBackToRecs,
  } = chatState

  // Track whether the user has sent their first message (not just received the welcome bot msg)
  const [userInteracted, setUserInteracted] = useState(false)

  const handleSend = useCallback((text) => {
    setUserInteracted(true)
    sendMessage(text)
  }, [sendMessage])

  const handleSendImage = useCallback((data) => {
    setUserInteracted(true)
    sendImage(data)
  }, [sendImage])

  // Intercept voice commands — "download" triggers PDF, everything else sends normally
  const handleVoiceTranscript = useCallback((text) => {
    if (/\bdownload\b/i.test(text) && lastBookingCard) {
      generateBookingPDF(lastBookingCard)
      return
    }
    setUserInteracted(true)
    sendMessage(text)
  }, [sendMessage, lastBookingCard])

  const { sttSupported, isListening, isTtsPlaying, interimText, toggleMic } =
    useVoice(handleVoiceTranscript, lastBotText, sessionId)

  const vehicleSentRef = useRef(false)

  useEffect(() => {
    if (initialVehicle && !vehicleSentRef.current) {
      vehicleSentRef.current = true
      setUserInteracted(true)
      setTimeout(() => sendMessage(`I'm looking for tyres for a ${initialVehicle}`), 400)
    }
  }, [initialVehicle]) // eslint-disable-line

  const showHero = !userInteracted

  return (
    <div className="agent-page">
      <SharedHeader
        activePage="agent"
        stage={stage}
        member={member}
        onSwitchToAgent={onSwitchToAgent}
        onSwitchToStore={onSwitchToStore}
        onSwitchToDashboard={onSwitchToDashboard}
      />

      <div className="agent-bg">
        <div className="agent-card">

          {/* Header — large hero on landing, compact after first interaction */}
          <div className={`agent-card-title-wrap${showHero ? ' hero' : ' compact'}`}>
            <img src="/tyre_assist.svg" alt="TireAssist" className="agent-header-img" />
            <div className="agent-header-text">
              <h1 className="agent-card-title">TireAssist</h1>
              {showHero && <p className="agent-header-sub">Your AI Tyre Executive Assistant</p>}
            </div>
          </div>

          {/* Messages */}
          <ChatFeed
            messages={messages}
            isTyping={isTyping}
            onSendMessage={handleSend}
            onFeedback={sendFeedback}
            onBackToRecs={goBackToRecs}
          />

          {/* Input */}
          <ChatInput
            onSend={handleSend}
            onSendImage={handleSendImage}
            isTyping={isTyping}
            sttSupported={sttSupported}
            isListening={isListening}
            isTtsPlaying={isTtsPlaying}
            interimText={interimText}
            onToggleMic={toggleMic}
          />

        </div>
      </div>
    </div>
  )
}
