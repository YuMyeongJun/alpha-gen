import axios from "axios";

const apiClient = axios.create({
  baseURL: "",
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "API 요청 실패";
    return Promise.reject(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)));
  },
);

export default apiClient;
