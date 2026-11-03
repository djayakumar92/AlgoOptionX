import { Component } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
class Boundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<main className="identity-page" role="alert"><h1>This screen could not be displayed</h1><p>Your saved data remains on the server. Return home or reload the screen.</p><div className="identity-links"><Link to="/">Product home</Link><button onClick={()=>window.location.reload()}>Reload screen</button></div></main>:this.props.children;}
}
export default function ScreenBoundary({children}:{children:ReactNode}){const location=useLocation();return <Boundary key={location.pathname}>{children}</Boundary>;}
