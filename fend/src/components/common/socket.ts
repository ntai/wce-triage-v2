import { io, Socket } from "socket.io-client";
import { sweetHome } from "../../looseend/home";
import { SocketEventMap } from "../../types/socket-events";

type ListenEvents = { [K in keyof SocketEventMap]: (payload: SocketEventMap[K]) => void };

// One shared connection for the whole app, typed against SocketEventMap so
// socket.on(event, ...) / socket.off(event, ...) get compile-time-checked
// event names and payloads.
export const socket: Socket<ListenEvents> = io(sweetHome.websocketUrl);
