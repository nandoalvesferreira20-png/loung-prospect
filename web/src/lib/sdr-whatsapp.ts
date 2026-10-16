// Phone is normalized by the shared Python domain; never guess DDI in the browser.
export function whatsappLink(phone: string | null, message: string): string | null {
  if (!phone || !/^[1-9]\d{7,14}$/.test(phone) || !message.trim() || [...message].length > 1200) return null;
  return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
}
