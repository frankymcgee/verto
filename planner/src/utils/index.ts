import { toast } from "frappe-ui";

export { default as dayjs } from "./dayjs";

export const raiseToast = (type: "success" | "error", message: string) => {
  const div = document.createElement("div");
  div.innerHTML = message;
  const text =
    div.textContent || "Failed to perform action. Please try again later.";
  return toast[type](text, { duration: type === "error" ? 7000 : 4000 });
};

export const goTo = (path: string) => {
  window.location.href = path;
};
