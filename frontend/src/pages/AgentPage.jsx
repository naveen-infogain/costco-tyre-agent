import { useEffect, useRef, useCallback } from 'react'
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

  // Intercept voice commands before they reach sendMessage:
  // "download" → trigger PDF if booking is confirmed; everything else passes through normally.
  const handleVoiceTranscript = useCallback((text) => {
    if (/\bdownload\b/i.test(text) && lastBookingCard) {
      generateBookingPDF(lastBookingCard)
      return
    }
    sendMessage(text)
  }, [sendMessage, lastBookingCard])

  const { sttSupported, isListening, isTtsPlaying, interimText, toggleMic } =
    useVoice(handleVoiceTranscript, lastBotText, sessionId)

  const vehicleSentRef = useRef(false)

  useEffect(() => {
    if (initialVehicle && !vehicleSentRef.current) {
      vehicleSentRef.current = true
      setTimeout(() => sendMessage(`I'm looking for tyres for a ${initialVehicle}`), 400)
    }
  }, [initialVehicle]) // eslint-disable-line

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

          {/* Title — full on empty state, compact single-line once chat starts */}
          <div className={`agent-card-title-wrap${messages.length > 0 ? ' compact' : ''}`}>
            <h1 className="agent-card-title">
              {messages.length > 0
                ? 'Meet TireAssist, Your AI Executive Assistant'
                : <> Meet TireAssist,<br />Your AI Executive Assistant </>
              }
            </h1>
          </div>

          {/* Messages */}
          <ChatFeed
            messages={messages}
            isTyping={isTyping}
            onSendMessage={sendMessage}
            onFeedback={sendFeedback}
            onBackToRecs={goBackToRecs}
          />

          {/* Input */}
          <ChatInput
            onSend={sendMessage}
            onSendImage={sendImage}
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
