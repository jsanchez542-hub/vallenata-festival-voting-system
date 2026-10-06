import { getState, persist, newId, getSessionUserId, setSessionUserId } from "./storage.js";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const MIN_PASSWORD_LENGTH = 8;

export function currentUser() {
  const userId = getSessionUserId();
  if (!userId) return null;
  return getState().users.find((user) => user.id === userId && user.active) ?? null;
}

export function validateRegistration({ name, email, password }) {
  const errors = {};
  if (name.trim().length < 3) errors.name = "Escribe tu nombre completo, con al menos 3 caracteres.";
  if (!EMAIL_PATTERN.test(email.trim())) errors.email = "Escribe un correo válido, por ejemplo nombre@correo.com.";
  if (password.length < MIN_PASSWORD_LENGTH) errors.password = `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  return errors;
}

export function registerUser({ name, email, password }) {
  const errors = validateRegistration({ name, email, password });
  const normalizedEmail = email.trim().toLowerCase();
  const { users } = getState();
  if (!errors.email && users.some((user) => user.email === normalizedEmail)) {
    errors.email = "Ya existe una cuenta con este correo. Ingresa o usa otro correo.";
  }
  if (Object.keys(errors).length > 0) return { ok: false, errors };

  const user = {
    id: newId("user"),
    name: name.trim(),
    email: normalizedEmail,
    password,
    role: "voter",
    active: true,
    createdAt: Date.now(),
  };
  users.push(user);
  persist();
  setSessionUserId(user.id);
  return { ok: true, user };
}

export function signIn(email, password) {
  const normalizedEmail = email.trim().toLowerCase();
  const user = getState().users.find((candidate) => candidate.email === normalizedEmail);
  if (!user || user.password !== password || !user.active) {
    return { ok: false, error: "El correo o la contraseña no coinciden. Revisa los datos e inténtalo de nuevo." };
  }
  setSessionUserId(user.id);
  return { ok: true, user };
}

export function signOut() {
  setSessionUserId(null);
}
