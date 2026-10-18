import { redirect } from "react-router";

import { langFromRequest, localizePath, makeT } from "./index";

/** t() для loaders/actions по языку запроса */
export function serverT(request: Request) {
  return makeT(langFromRequest(request));
}

/** redirect с сохранением языка: на /ru/... странице ведёт на /ru/<path> */
export function localRedirect(request: Request, path: string, init?: number | ResponseInit) {
  return redirect(localizePath(langFromRequest(request), path), init);
}
