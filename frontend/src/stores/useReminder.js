/**
 * Reminder system — schedules personality-driven prompts at fixed times of
 * day plus periodic nudges (water/move/eyes/random) plus a one-shot
 * birthday check on init.
 *
 * Compared with the original App.vue:
 *   - Centralised timer ownership so cleanup is a single call.
 *   - `scheduleDailyReminders` no longer recursively re-schedules the full
 *     day on every fire; it walks one slot at a time.
 *   - The personality is read live from useSettings, so flipping it in the
 *     UI takes effect on the next reminder without a restart.
 */

import { ref } from 'vue'
import { reminderMessages } from '../data/reminderMessages.js'
import { useSettings } from './useSettings.js'

const interactionMessage = ref('')
const showInteractionBubble = ref(false)
let interactionTimer = null

const timers = []

// FIFO queue for concurrent reminders so two timers that fire on the same
// tick (e.g. hourly drinkWater + move) don't clobber each other — the
// previous bug was that show() always cleared the current message, so the
// second reminder ate the first one within the same animation frame.
const messageQueue = []
const VISIBLE_MS = 5000
const GAP_MS = 400

function clearAll() {
  for (const t of timers) {
    clearTimeout(t)
    clearInterval(t)
  }
  timers.length = 0
  if (interactionTimer) {
    clearTimeout(interactionTimer)
    interactionTimer = null
  }
  messageQueue.length = 0
}

function drainQueue() {
  if (interactionTimer || messageQueue.length === 0) return
  const msg = messageQueue.shift()
  interactionMessage.value = msg
  showInteractionBubble.value = true
  interactionTimer = setTimeout(() => {
    showInteractionBubble.value = false
    interactionMessage.value = ''
    interactionTimer = null
    // Small gap so transitions don't visually collide.
    setTimeout(drainQueue, GAP_MS)
  }, VISIBLE_MS)
}

function show(message) {
  if (!message) return
  messageQueue.push(message)
  drainQueue()
}

function pickPersonalityVariant(slot) {
  const { personality } = useSettings()
  return slot[personality.value] || slot.gentle
}

/**
 * Time slots ordered by hour; each entry is { hour, minute, period, key }.
 * `findNextSlot` returns the first slot whose target time is in the future.
 */
const DAILY_SLOTS = [
  { hour: 6,  minute: 30, period: 'morning',   key: 'wakeup' },
  { hour: 7,  minute: 0,  period: 'morning',   key: 'breakfast' },
  { hour: 7,  minute: 30, period: 'morning',   key: '出门' },
  { hour: 9,  minute: 0,  period: 'forenoon',  key: 'work' },
  { hour: 10, minute: 30, period: 'forenoon',  key: 'snack' },
  { hour: 12, minute: 0,  period: 'noon',      key: 'lunch' },
  { hour: 13, minute: 0,  period: 'noon',      key: 'nap' },
  { hour: 14, minute: 0,  period: 'afternoon', key: 'work' },
  { hour: 15, minute: 30, period: 'afternoon', key: 'tea' },
  { hour: 17, minute: 30, period: 'afternoon', key: 'offWork' },
  { hour: 18, minute: 0,  period: 'evening',   key: 'dinner' },
  { hour: 19, minute: 30, period: 'evening',   key: 'exercise' },
  { hour: 21, minute: 30, period: 'evening',   key: 'bedtime' },
  { hour: 23, minute: 0,  period: 'midnight',  key: 'stayUp' },
  { hour: 24, minute: 0,  period: 'midnight',  key: 'forcedSleep' }, // end-of-day rollover
]

function nextSlotDelay() {
  const now = new Date()
  for (const slot of DAILY_SLOTS) {
    const target = new Date()
    if (slot.hour === 24) {
      target.setDate(target.getDate() + 1)
      target.setHours(0, 0, 0, 0)
    } else {
      target.setHours(slot.hour, slot.minute, 0, 0)
    }
    const delay = target.getTime() - now.getTime()
    if (delay > 0) return { slot, delay }
  }
  // After the last slot, schedule the first slot of the next day.
  const target = new Date()
  target.setDate(target.getDate() + 1)
  target.setHours(DAILY_SLOTS[0].hour, DAILY_SLOTS[0].minute, 0, 0)
  return { slot: DAILY_SLOTS[0], delay: target.getTime() - now.getTime() }
}

function scheduleNextDaily() {
  const { slot, delay } = nextSlotDelay()
  const t = setTimeout(() => {
    const variants = reminderMessages[slot.period]?.[slot.key]
    if (variants) show(pickPersonalityVariant(variants))
    scheduleNextDaily()
  }, delay)
  timers.push(t)
}

function startPeriodic() {
  const periodicShow = (key, intervalMs) => {
    const id = setInterval(() => {
      const variants = reminderMessages.periodic[key]
      if (variants) show(pickPersonalityVariant(variants))
    }, intervalMs)
    timers.push(id)
  }

  periodicShow('drinkWater', 60 * 60 * 1000)         // hourly
  periodicShow('move',       60 * 60 * 1000)         // hourly
  periodicShow('eyeCare',    2 * 60 * 60 * 1000)     // every 2h

  const randomId = setInterval(() => {
    const list = reminderMessages.random
    if (list?.length) show(list[Math.floor(Math.random() * list.length)])
  }, 30 * 60 * 1000)   // every 30 min — used to be 60s which was spammy
  timers.push(randomId)
}

function checkBirthday() {
  const { birthday } = useSettings()
  if (!birthday.value) return
  const parts = birthday.value.split('-')
  if (parts.length < 3) return
  const now = new Date()
  if (parseInt(parts[1], 10) === now.getMonth() + 1 && parseInt(parts[2], 10) === now.getDate()) {
    const variants = reminderMessages.special.birthday
    if (variants) show(pickPersonalityVariant(variants))
  }
}

function start() {
  clearAll()
  scheduleNextDaily()
  startPeriodic()
  checkBirthday()
}

export function useReminder() {
  return {
    interactionMessage,
    showInteractionBubble,
    show,
    start,
    clearAll,
  }
}
