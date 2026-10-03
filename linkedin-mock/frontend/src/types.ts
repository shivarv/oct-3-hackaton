export interface UserSummary {
  id: string;
  name: string;
  headline: string;
}

export type Gender = "female" | "male" | "non_binary" | "other" | "prefer_not_to_say";

export const GENDER_LABELS: Record<Gender, string> = {
  female: "Female",
  male: "Male",
  non_binary: "Non-binary",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

export interface ResumeInfo {
  filename: string;
  size: number;
  uploaded_at: string;
}

/** phone, age, gender and date_of_birth are only filled in for the logged-in member. */
export interface User extends UserSummary {
  username: string | null;
  location: string;
  about: string;
  phone: string;
  age: number | null;
  gender: Gender | null;
  date_of_birth: string | null; // YYYY-MM-DD
  resume: ResumeInfo | null;
  connections: string[];
}

export interface SignupInput {
  name: string;
  username: string;
  password: string;
  headline: string;
  location: string;
}

/** Partial update: omitted fields are unchanged, null clears an optional field. */
export interface UserUpdate {
  name?: string;
  username?: string;
  headline?: string;
  location?: string;
  about?: string;
  phone?: string;
  age?: number | null;
  gender?: Gender | null;
  date_of_birth?: string | null;
}

export interface Comment {
  id: string;
  author: UserSummary;
  text: string;
  created_at: string;
}

export interface Post {
  id: string;
  author: UserSummary;
  content: string;
  created_at: string;
  edited_at: string | null;
  likes: string[];
  comments: Comment[];
}

export type View =
  | { page: "feed" }
  | { page: "network" }
  | { page: "settings" }
  | { page: "profile"; userId: string };
