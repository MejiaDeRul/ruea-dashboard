import React from "react";

type State = { hasError: boolean; error?: any };

export default class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { hasError: false };
  static getDerivedStateFromError(error: any) { return { hasError: true, error }; }
  componentDidCatch(error: any, info: any) { console.error("[ErrorBoundary]", error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{padding:16}}>
          <h1>Se produjo un error en la UI</h1>
          <pre style={{whiteSpace:"pre-wrap", background:"#fff6f6", padding:12, borderRadius:8, border:"1px solid #ffdede"}}>
            {String(this.state.error ?? "Unknown error")}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
