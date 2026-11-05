// Loaded by Frappe's existing Socket.IO service (restart it after deploying).
const ROOM = "verto:planner";

module.exports = function plannerHandlers(socket) {
  let subscribing = null;
  let generation = 0;

  socket.on("verto:planner_subscribe", async (ack) => {
    const reply = typeof ack === "function" ? ack : () => {};
    if (!socket.user || socket.user === "Guest") return reply({ ok: false });
    const attempt = generation;
    try {
      // One permission request per subscription attempt, shared across duplicate
      // emits. Never accept a room name or user identity supplied by the client.
      if (!subscribing) {
        subscribing = socket.frappe_request("/api/method/verto.api.planner_realtime.can_subscribe")
          .then((response) => response.ok ? response.json() : { message: false })
          .then((response) => response.message === true || response.message === 1)
          .finally(() => { subscribing = null; });
      }
      const allowed = await subscribing;
      if (!allowed || !socket.connected || attempt !== generation) return reply({ ok: false });
      await socket.join(ROOM);
      reply({ ok: true });
    } catch {
      reply({ ok: false });
    }
  });
  socket.on("verto:planner_unsubscribe", () => {
    generation++;
    socket.leave(ROOM);
  });
  socket.on("disconnect", () => { generation++; });
};
