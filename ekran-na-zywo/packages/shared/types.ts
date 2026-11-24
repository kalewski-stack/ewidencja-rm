// Wspólne typy i protokół (frontend + worker). Jedno źródło prawdy o kształcie stanu.

export type PhoneMode = 'waiting' | 'poll' | 'questions' | 'thanks' | 'closed';
export const PHONE_MODES: PhoneMode[] = ['waiting', 'poll', 'questions', 'thanks', 'closed'];

export type SceneId =
  | 'idle'
  | 'infographics'
  | 'qr'
  | 'poll_live'
  | 'poll_result'
  | 'questions_collect'
  | 'question_focus'
  | 'recommendations'
  | 'summary'
  | 'blackout';
export const SCENES: SceneId[] = [
  'idle', 'infographics', 'qr', 'poll_live', 'poll_result',
  'questions_collect', 'question_focus', 'recommendations', 'summary', 'blackout',
];

export type Role = 'public' | 'screen' | 'mod' | 'ops';

export interface PollOption { id: string; label: string }
export interface Poll {
  id: string;
  text: string;
  options: PollOption[];
  tally: Record<string, number>; // same sumy, bez powiązania z osobami
  frozenResult?: { tally: Record<string, number>; total: number; at: string };
  manualOverride?: Record<string, number>; // wpis ręczny (podniesione ręce)
}

export type QuestionStatus = 'new' | 'approved' | 'on_screen' | 'answered' | 'hidden' | 'duplicate';
export interface Question {
  id: string;
  text: string;
  originalText?: string;
  name?: string;
  expertId?: string;
  status: QuestionStatus;
  duplicateOf?: string;
  flagged?: boolean; // trafienie w blocklist
  approvedAt?: string;
  createdAt: string;
  source: 'phone' | 'manual';
}

export interface Expert { id: string; name: string; role?: string }
export interface Recommendation { title: string; text: string; rev: number }

export interface SlideBase {
  id?: string;
  type: 'bigNumber' | 'bar' | 'line' | 'map' | 'compare';
  title: string;
  source: string;
  year: number | string | null;
  verified: boolean;
  notes: string;
  seconds?: number;
  unit?: string;
  caption?: string;
}
export interface SlideBigNumber extends SlideBase { type: 'bigNumber'; value: number | null; decimals?: number }
export interface SlideBar extends SlideBase { type: 'bar'; categories: { label: string; value: number }[] }
export interface SlideLine extends SlideBase { type: 'line'; x: (number | string)[]; series: { name: string; values: number[] }[] }
export interface SlideMap extends SlideBase { type: 'map'; values: Record<string, number> }
export interface CompareSide { value: number | null; unit?: string; label: string }
export interface SlideCompare extends SlideBase { type: 'compare'; left: CompareSide; right: CompareSide }
export type Slide = SlideBigNumber | SlideBar | SlideLine | SlideMap | SlideCompare;

export interface SceneParams {
  slideIndex?: number;
  slideNonce?: number; // rośnie przy ręcznym skoku, ekran wtedy przeskakuje
  questionId?: string;
  revealCount?: number;
}

/** Pełny stan (widok ops i mod). */
export interface State {
  version: number;
  phoneMode: PhoneMode;
  scene: SceneId;
  sceneParams: SceneParams;
  pollStatus: 'draft' | 'open' | 'closed';
  pollEpoch: number; // rośnie po wyzerowaniu, telefony mogą wtedy głosować od nowa
  polls: Poll[];
  activePoll: number; // które pytanie ankiety pokazuje ekran
  questions: Question[];
  queue: string[]; // kolejka "Na panel" (id pytań, w kolejności)
  experts: Expert[];
  recommendations: Recommendation[]; // 5 slotów
  counters: { votes: number; questionsSubmitted: number };
  fallbackStatic: boolean;
  slides: Slide[];
  slidesPaused: boolean;
  slidesCustom: boolean; // wgrane z /ops zamiast z content/slides.json
  agendaStep: number;
  lastSavedAt: string;
}

export interface Presence {
  phones: number;
  screens: number;
  mods: number;
  ops: number;
  screenBeatAt: number; // ms, ostatni heartbeat z /screen (0 = brak)
  screenSlide: number;
}

export interface PublicView {
  role: 'public';
  version: number;
  phoneMode: PhoneMode;
  pollStatus: State['pollStatus'];
  pollEpoch: number;
  polls: { id: string; text: string; options: PollOption[] }[];
  experts: Expert[];
}

export interface ScreenQuestion { id: string; text: string; name?: string; expertId?: string }
export interface ScreenView {
  role: 'screen';
  version: number;
  scene: SceneId;
  sceneParams: SceneParams;
  phoneMode: PhoneMode;
  pollStatus: State['pollStatus'];
  poll: { id: string; text: string; options: PollOption[]; tally: Record<string, number>; total: number; frozen: boolean };
  votes: number;
  questionsSubmitted: number;
  approved: ScreenQuestion[]; // wyłącznie zatwierdzone, w kolejności zatwierdzania
  focus: ScreenQuestion | null;
  experts: Expert[];
  recommendations: { title: string; text: string }[];
  slides: Slide[];
  slidesPaused: boolean;
  fallbackStatic: boolean;
  publicUrl: string;
}

export interface StaffView extends State {
  role: 'mod' | 'ops';
  presence: Presence;
  publicUrl: string;
  buildVersion: string;
}

export type View = PublicView | ScreenView | StaffView;

// ---- wiadomości WebSocket ----
export type ClientMsg =
  | { t: 'hello'; role: Role; token?: string; version?: number; preview?: boolean }
  | { t: 'ping'; slide?: number }
  | { t: 'cmd'; id: string; type: string; payload?: Record<string, unknown> };

export type ServerMsg =
  | { t: 'state'; version: number; view: View }
  | { t: 'ack'; id: string; data?: unknown }
  | { t: 'error'; id?: string; code: string; message: string }
  | { t: 'pong' };

export const REC_TITLE_MAX = 60;
export const REC_TEXT_MAX = 140;
