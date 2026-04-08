import { useEffect, useRef } from 'react'
import BotBubble from './messages/BotBubble'
import UserBubble from './messages/UserBubble'
import TypingIndicator from './messages/TypingIndicator'
import CardsGrid from './cards/CardsGrid'
import SlotPicker from './cards/SlotPicker'
import BookingCard from './cards/BookingCard'
import QuickReplies from './QuickReplies'
import RecoveryBanner from './RecoveryBanner'

export default function ChatFeed({ messages, isTyping, onSendMessage, onFeedback }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  function renderMessage(msg) {
    switch (msg.type) {
      case 'user':
        return <UserBubble key={msg.id} text={msg.text} />

      case 'bot':
        return (
          <BotBubble
            key={msg.id}
            text={msg.text}
            onFeedback={(signal) => onFeedback(signal, null, 'orchestrator')}
          />
        )

      case 'cards':
        return (
          <CardsGrid
            key={msg.id}
            cards={msg.cards}
            onSendMessage={onSendMessage}
            onFeedback={onFeedback}
          />
        )

      case 'slots':
        return <SlotPicker key={msg.id} slots={msg.slots} onSendMessage={onSendMessage} />

      case 'booking':
        return <BookingCard key={msg.id} data={msg.data} />

      case 'quickreplies':
        return (
          <QuickReplies
            key={msg.id}
            replies={msg.replies}
            used={msg.used}
            onSend={onSendMessage}
          />
        )

      case 'recovery':
        return <RecoveryBanner key={msg.id} recovery={msg.recovery} />

      default:
        return null
    }
  }

  return (
    <div className="ta-feed" role="log" aria-live="polite">
      {messages.map(renderMessage)}
      {isTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
