const DIGITS = /\d+/;

export function parseRoomNumber(roomName) {
  const match = DIGITS.exec(roomName || "");
  return match ? Number.parseInt(match[0], 10) : 0;
}

export function sortSessions(sessions) {
  return [...sessions].sort((a, b) => {
    const numberA = a.room_number ?? parseRoomNumber(a.room_name);
    const numberB = b.room_number ?? parseRoomNumber(b.room_name);
    if (numberA !== numberB) return numberA - numberB;
    return (a.room_name || "").toLowerCase().localeCompare((b.room_name || "").toLowerCase());
  });
}

export function sortRooms(rooms) {
  return [...rooms].sort((a, b) => {
    const numberA = a.room_number ?? parseRoomNumber(a.room_name);
    const numberB = b.room_number ?? parseRoomNumber(b.room_name);
    if (numberA !== numberB) return numberA - numberB;
    return (a.room_name || "").toLowerCase().localeCompare((b.room_name || "").toLowerCase());
  });
}
