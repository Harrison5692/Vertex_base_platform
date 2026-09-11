import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { useAuth } from './auth'

const CART_KEY = 'vertex_cart'

function loadLocalCart() {
  try {
    const raw = localStorage.getItem(CART_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveLocalCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart))
}

function toLine(item, quantity) {
  return {
    item_id: item.id,
    name: item.name,
    unit_price: item.price ?? 0,
    quantity,
    image_url: item.image_url ?? null,
  }
}

/** Cart persistence: a logged-in account's cart lives on the server
 * (see /cart/) so it follows them across devices/browsers. A guest
 * (not logged in) still uses localStorage — that already survives
 * closing the tab and coming back later, in the SAME browser; it
 * just can't follow someone to a different device, which needs an
 * account (some identifier) to do safely — see the conversation this
 * was decided in for why IP-based guest persistence isn't a good
 * substitute.
 *
 * The moment someone logs in, whatever's sitting in their local cart
 * gets merged into their server cart once (summed with any existing
 * server-side quantities), then localStorage is cleared and the
 * server becomes the source of truth for the rest of the session. */
export function useCart() {
  const { user } = useAuth()
  const [cart, setCart] = useState(() => (user ? [] : loadLocalCart()))
  const [loading, setLoading] = useState(!!user)
  const mergedForUserId = useRef(null)

  useEffect(() => {
    if (!user) {
      mergedForUserId.current = null
      setCart(loadLocalCart())
      setLoading(false)
      return
    }
    if (mergedForUserId.current === user.id) return
    mergedForUserId.current = user.id

    setLoading(true)
    api
      .get('/cart/')
      .then((serverCart) => {
        const localCart = loadLocalCart()
        if (localCart.length === 0) return serverCart

        const merged = serverCart.map((line) => ({ ...line }))
        for (const localLine of localCart) {
          const existing = merged.find((line) => line.item_id === localLine.item_id)
          if (existing) existing.quantity += localLine.quantity
          else merged.push(localLine)
        }
        return api.put('/cart/', {
          lines: merged.map(({ item_id, quantity }) => ({ item_id, quantity })),
        })
      })
      .then((finalCart) => {
        setCart(finalCart)
        localStorage.removeItem(CART_KEY)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  function persist(next) {
    setCart(next)
    if (user) {
      api
        .put('/cart/', { lines: next.map(({ item_id, quantity }) => ({ item_id, quantity })) })
        .catch(() => {})
    } else {
      saveLocalCart(next)
    }
  }

  function addToCart(item) {
    const existing = cart.find((line) => line.item_id === item.id)
    const next = existing
      ? cart.map((line) =>
          line.item_id === item.id ? { ...line, quantity: line.quantity + 1 } : line
        )
      : [...cart, toLine(item, 1)]
    persist(next)
  }

  function updateQuantity(itemId, quantity) {
    const q = Math.max(1, Number(quantity) || 1)
    persist(cart.map((line) => (line.item_id === itemId ? { ...line, quantity: q } : line)))
  }

  function removeFromCart(itemId) {
    persist(cart.filter((line) => line.item_id !== itemId))
  }

  function clearCart() {
    persist([])
  }

  return { cart, loading, addToCart, updateQuantity, removeFromCart, clearCart }
}
