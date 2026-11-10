export const initialStore = () => {
  return {
    message: null,
    token: localStorage.getItem("token") || null,
    user: localStorage.getItem("user") || null,
  };
};

export default function storeReducer(store, action = {}) {
  switch (action.type) {
    case "login":
      return {
        ...store,
        token: action.payload.token,
        user: action.payload.user,
      };
    case "logout":
      return {
        ...store,
        token: null,
        user: null,
      };
    default:
      throw Error("unknown action");
  }
}
