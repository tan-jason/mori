export const BASE_LANGUAGE = {
  id: "english",
  name: "English",
} as const;

export const TARGET_LANGUAGES = [
  {
    id: "mandarin",
    name: "Mandarin",
    courseName: "Standard Mandarin",
    nativeName: "中文",
    greeting: "Nǐ hǎo",
    mark: "中",
  },
  {
    id: "spanish",
    name: "Spanish",
    courseName: "Spanish",
    nativeName: "Español",
    greeting: "Hola",
    mark: "ES",
  },
  {
    id: "french",
    name: "French",
    courseName: "French",
    nativeName: "Français",
    greeting: "Bonjour",
    mark: "FR",
  },
  {
    id: "portuguese",
    name: "Portuguese",
    courseName: "Portuguese",
    nativeName: "Português",
    greeting: "Olá",
    mark: "PT",
  },
  {
    id: "japanese",
    name: "Japanese",
    courseName: "Japanese",
    nativeName: "日本語",
    greeting: "Konnichiwa",
    mark: "日",
  },
  {
    id: "korean",
    name: "Korean",
    courseName: "Korean",
    nativeName: "한국어",
    greeting: "Annyeonghaseyo",
    mark: "한",
  },
  {
    id: "vietnamese",
    name: "Vietnamese",
    courseName: "Vietnamese",
    nativeName: "Tiếng Việt",
    greeting: "Xin chào",
    mark: "Vi",
  },
] as const;

export type TargetLanguageId = (typeof TARGET_LANGUAGES)[number]["id"];
export type TargetLanguage = (typeof TARGET_LANGUAGES)[number];

export interface LanguageProfile {
  id: string;
  baseLanguageId: typeof BASE_LANGUAGE.id;
  targetLanguageId: TargetLanguageId;
}

export const DEFAULT_TARGET_LANGUAGE_ID: TargetLanguageId = "mandarin";

export function isTargetLanguageId(value: string): value is TargetLanguageId {
  return TARGET_LANGUAGES.some((language) => language.id === value);
}

export function getTargetLanguage(id: TargetLanguageId): TargetLanguage {
  const language = TARGET_LANGUAGES.find((candidate) => candidate.id === id);

  if (!language) {
    throw new Error(`Unsupported target language: ${id}`);
  }

  return language;
}
