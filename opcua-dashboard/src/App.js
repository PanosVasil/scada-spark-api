import React, { useEffect, useState, useCallback, useRef, memo, createContext, useContext } from 'react';

// --- CONFIGURATION ---
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL_BASE = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

// ===============================================
// 1. AUTHENTICATION CONTEXT & PROVIDER
// ===============================================
const AuthContext = createContext(null);

const AuthProvider = ({ children }) => {
    const [token, setToken] = useState(() => localStorage.getItem('authToken'));

    const login = (newToken) => {
        localStorage.setItem('authToken', newToken);
        setToken(newToken);
    };

    const logout = useCallback(() => {
        localStorage.removeItem('authToken');
        setToken(null);
    }, []);

    const authContextValue = { token, login, logout };

    return <AuthContext.Provider value={authContextValue}>{children}</AuthContext.Provider>;
};

const useAuth = () => {
    return useContext(AuthContext);
};


// ===============================================
// 2. LOGIN PAGE COMPONENT
// ===============================================
const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        
        try {
            const response = await fetch(`${API_URL}/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ username, password })
            });

            if (!response.ok) {
                throw new Error('Login failed. Please check your username and password.');
            }

            const data = await response.json();
            login(data.access_token);

        } catch (err) {
            setError(err.message || 'An unknown error occurred.');
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100">
            <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-sm">
                <h1 className="text-2xl font-bold text-center text-gray-800 mb-6">OPC-UA Dashboard Login</h1>
                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="username">Username</label>
                        <input id="username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full p-2 border rounded-md" required />
                    </div>
                    <div className="mb-6">
                        <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">Password</label>
                        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full p-2 border rounded-md" required />
                    </div>
                    {error && <p className="text-red-500 text-xs italic mb-4">{error}</p>}
                    <button type="submit" className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md">
                        Login
                    </button>
                </form>
            </div>
        </div>
    );
};


// ===============================================
// 3. DASHBOARD PAGE (Contains all previous components)
// ===============================================
const DashboardPage = () => {
  const { token, logout } = useAuth();
  
  // --- Categorization, Formatters, Writeable Components etc. ---
  const measurementNodes = new Set(['Active_Power_Measurement', 'Reactive_Power_Measurement', 'Ouput_Current_Phase_1_Measurement', 'Ouput_Current_Phase_2_Measurement', 'Ouput_Current_Phase_3_Measurement', 'Ouput_Voltage_Phase_1_Measurement', 'Ouput_Voltage_Phase_2_Measurement', 'Ouput_Voltage_Phase_3_Measurement', 'Output_Frequency_Measurement', 'Power_Factor_Cosφ_Measurement', 'Maximum_Production_Capacity', 'Station_Operating_Status']);
  const digitalSignalNodes = new Set(['CB_Status(Open/Closed)', 'CB_Control_Status(Remote/Local)', 'Earthing_Switch_Status(Open/Closed)', 'Equipment_Control_Status(Remote/Local)', 'Protection_Relay_Health_Status', 'Communication_Error(Production Equipment)', 'Overcurrent_Phase_1', 'Overcurrent_Phase_2', 'Overcurrent_Phase_3', 'Fault_To_Ground_Phase 1', 'Fault_To_Ground_Phase 2', 'Fault_To_Ground_Phase 3', 'Overvoltage', 'Undervoltage', 'Overfrequency', 'Underfrequency', 'Homopolar_Voltage_Protection', 'RoCoF', 'Equipment_Diagnostic_Status', 'Active_Power_Setpoint_Received_Confirmation', 'Instant_Cutoff_Command_Received_Confirmation', 'Reactive_Power_Setpoint_Received_Confirmation', 'Cosφ_Setpoint_Received_Confirmation', 'Active_Power_Setpoint_Third_Party', 'Reactive_Power_Setpoint_Third_Party', 'Cosφ_Setpoint_Third_Party', 'Cosφ=f(P)_Function_Third_Party', 'U(Q)_Function_Third_Party', 'LSFM-O_Function_Active', 'FSM_Function_Active', 'LFSM-U_Function_Active', 'Backup_Function_Active', 'Backup_Second_Function_Active']);
  const commandNodes = new Set(['CMD_CB_Status(Open/Close)', 'CMD_Enable_Reactive_Power_Setpoint', 'CMD_Enable_Cosφ=f(P)_Curve', 'CMD_Enable_U(Q)_Curve', 'CMD_Enable_LSFM-O', 'CMD_Enable_FSM', 'CMD_Enable_LFSM-U', 'CMD_Enable_Backup_Function', 'CMD_Enable_Second_Backup_Function', 'CMD_Reactive_Power_Setpoint', 'CMD_Cosφ_Setpoint', 'CMD_Set_Station_Operating_Function']);
  const userCommandNodes = new Set(['CMD_Active_Power_Setpoint_kW', 'CMD_Active_Power_Setpoint_%', 'CMD_Instant_Cutoff']);
  const writeableNodes = new Set(['CMD_Active_Power_Setpoint_kW', 'CMD_Active_Power_Setpoint_%', 'CMD_Instant_Cutoff']);
  const formatValue = (nodeName, value) => { if (value === 'True' || value === 'False') { const isTrue = value === 'True'; return <span className={`px-2 py-1 text-xs font-bold rounded-md ${isTrue ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{isTrue ? 'ON' : 'OFF'}</span>; } if (typeof value === 'string' && value.startsWith('[')) { try { const arr = JSON.parse(value.replace(/'/g, '"')); return <div className="flex items-center justify-center space-x-2">{arr.map((val, index) => <span key={index} className={`px-2 py-0.5 rounded-full text-xs font-semibold ${val ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>{`[${index}]: ${val ? 'ON' : 'OFF'}`}</span>)}</div>; } catch (e) { return <span className="text-gray-500">{value}</span>; } } const numericValue = parseFloat(value); if (!isNaN(numericValue)) { return numericValue; } return <span className="text-gray-800">{value}</span>; };
  const WriteableSetpoint = ({ plcUrl, nodeName }) => { const [inputValue, setInputValue] = useState(''); const [writeStatus, setWriteStatus] = useState('idle'); const handleWrite = async () => { if (inputValue === '') return; setWriteStatus('writing'); try { const response = await fetch(`${API_URL}/write_value`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ plc_url: plcUrl, node_name: nodeName, value: parseFloat(inputValue) }) }); if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.detail || 'Write failed'); } setWriteStatus('success'); setInputValue(''); } catch (error) { console.error('Write error:', error); setWriteStatus('error'); } setTimeout(() => setWriteStatus('idle'), 2000); }; const buttonStyles = { writing: 'bg-yellow-500', success: 'bg-green-500', error: 'bg-red-500', idle: 'bg-blue-500 hover:bg-blue-600' }; const buttonText = { writing: '...', success: 'OK!', error: 'Fail!', idle: 'Set' }; return (<div className="flex items-center space-x-2 justify-end"><input type="number" placeholder="New value..." value={inputValue} onChange={(e) => setInputValue(e.target.value)} className="w-24 p-2 border rounded-md text-right font-mono" /><button onClick={handleWrite} disabled={writeStatus === 'writing'} className={`w-14 px-3 py-2 text-white text-sm font-bold rounded-md transition-colors ${buttonStyles[writeStatus]}`}>{buttonText[writeStatus]}</button></div>); };
  const WriteableSwitch = ({ plcUrl, nodeName, currentValue }) => { const [isOn, setIsOn] = useState(false); const [writeStatus, setWriteStatus] = useState('idle'); useEffect(() => { try { const arr = JSON.parse(currentValue.replace(/'/g, '"')); setIsOn(arr[0] === true && arr[1] === false); } catch { setIsOn(false); } }, [currentValue]); const handleToggle = async () => { const newValue = !isOn; const valueToSend = newValue ? [true, false] : [false, true]; setWriteStatus('writing'); try { const response = await fetch(`${API_URL}/write_value`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ plc_url: plcUrl, node_name: nodeName, value: valueToSend }) }); if (!response.ok) { throw new Error('Write failed'); } setWriteStatus('success'); setIsOn(newValue); } catch (error) { console.error('Write error:', error); setWriteStatus('error'); } setTimeout(() => setWriteStatus('idle'), 1500); }; const statusText = isOn ? "Δικαίωμα Ένταξης ✅" : "Πλήρης Περικοπή"; const switchBg = isOn ? 'bg-green-500' : 'bg-red-500'; return (<div className="flex items-center justify-end space-x-3"><span className={`font-semibold text-sm ${isOn ? 'text-green-600' : 'text-red-700'}`}>{statusText}</span><button onClick={handleToggle} disabled={writeStatus === 'writing'} style={{ height: '16px', width: '28px' }} className={`relative inline-flex items-center rounded-full transition-colors ${switchBg}`}><span style={{ height: '12px', width: '12px', transform: isOn ? 'translateX(14px)' : 'translateX(2px)' }} className={`inline-block bg-white rounded-full transition-transform`} /></button></div>); };
  const Accordion = ({ title, children, count, defaultOpen = false }) => { const [isOpen, setIsOpen] = useState(defaultOpen); return (<div className="border rounded-lg mb-2 bg-white shadow-sm"><button onClick={() => setIsOpen(!isOpen)} className="w-full p-3 text-left font-semibold text-gray-700 flex justify-between items-center hover:bg-gray-50 rounded-lg"><span>{title} <span className="text-sm font-normal text-gray-500">({count} items)</span></span><span className={`transform transition-transform duration-200 ${isOpen ? 'rotate-180' : 'rotate-0'}`}><svg style={{ width: '1.25rem', height: '1.25rem' }} className="text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span></button>{isOpen && <div className="p-3 border-t">{children}</div>}</div>); };
  const LoadingSpinner = () => (<div className="text-center p-20 text-gray-500"><svg className="mx-auto h-12 w-12 text-gray-400 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><p className="mt-4 text-xl font-medium">Connecting...</p></div>);

  const useOpcUaWebSocket = (token, onAuthError) => {
      const [plcData, setPlcData] = useState([]); const [wsStatus, setWsStatus] = useState('Connecting...'); const ws = useRef(null);
      const connect = useCallback(() => {
          if (!token) return;
          const fullWsUrl = `${WS_URL_BASE}?token=${token}`;
          if (ws.current && ws.current.readyState < 2) return;
          ws.current = new WebSocket(fullWsUrl);
          ws.current.onopen = () => setWsStatus('Connected');
          ws.current.onmessage = (event) => { try { const data = JSON.parse(event.data); if (Array.isArray(data)) setPlcData(data); } catch (e) {} };
          ws.current.onclose = (event) => {
              if (event.code === 4001) { // Custom code for auth failure
                  console.error("WebSocket auth failed. Logging out.");
                  onAuthError(); 
              } else if (ws.current.onclose) { 
                  setWsStatus('Disconnected. Reconnecting...');
                  setTimeout(connect, 5000);
              }
          };
          ws.current.onerror = () => { if (ws.current.onclose) ws.current.close(); };
      }, [token, onAuthError]);
      useEffect(() => { connect(); return () => { if (ws.current) { ws.current.onclose = null; ws.current.close(); } }; }, [connect]);
      return { plcData, wsStatus };
  };
  
  const { plcData, wsStatus } = useOpcUaWebSocket(token, logout);
  const connectedPlcs = plcData.filter(p => p.status === 'CONNECTED').length;

  const PlcCard = memo(({ plc }) => {
    const isConnected = plc.status === 'CONNECTED';
    const statusStyles = { CONNECTED: 'bg-green-50 border-green-400', CONNECTING: 'bg-yellow-50 border-yellow-400', DISCONNECTED: 'bg-red-50 border-red-400', ERROR: 'bg-red-100 border-red-500' };
    const statusClass = statusStyles[plc.status] || 'bg-gray-100';
    const allNodes = Object.entries(plc.nodes || {});
    const measurements = allNodes.filter(([key]) => measurementNodes.has(key));
    const digitalSignals = allNodes.filter(([key]) => digitalSignalNodes.has(key));
    const commands = allNodes.filter(([key]) => commandNodes.has(key));
    const userCommands = allNodes.filter(([key]) => userCommandNodes.has(key));
    const renderNodeTable = (nodes, isUserCommandCategory = false) => (
      <table className="w-full text-sm table-fixed">
          <thead className="text-left text-xs text-gray-500 uppercase font-semibold"><tr><th className="py-2 px-6 w-1/2">Name</th><th className="py-2 px-6 text-center">Live Value</th>{isUserCommandCategory && <th className="py-2 px-6 text-right">Action</th>}</tr></thead>
          <tbody>
              {nodes.map(([name, value]) => {
                  const isWriteable = writeableNodes.has(name); const isSwitch = name === 'CMD_Instant_Cutoff';
                  return (<tr key={name} className="border-t hover:bg-gray-50">
                      <td className="py-3 px-6 font-medium text-gray-700 truncate">{name.replace(/_/g, ' ')}</td>
                      {isUserCommandCategory && isWriteable ? (<>
                          <td className="py-3 px-6 text-center font-mono align-middle">{formatValue(name, value)}</td>
                          <td className="py-3 px-6 text-right">{isSwitch ? <WriteableSwitch plcUrl={plc.url} nodeName={name} currentValue={value} token={token} /> : <WriteableSetpoint plcUrl={plc.url} nodeName={name} token={token} />}</td>
                      </>) : (<td className="py-3 px-6 text-right font-mono align-middle" colSpan={2}>{formatValue(name, value)}</td>)}
                  </tr>);
              })}
          </tbody>
      </table>);
    return (<div className={`p-4 rounded-lg shadow-md border ${statusClass}`}><div className="mb-4"><h2 className="text-xl font-bold text-gray-800 truncate" title={plc.name}>{plc.name}</h2><div className="text-sm font-semibold text-gray-500">Status: <span className="font-bold text-gray-800">{plc.status}</span></div></div>{isConnected && allNodes.length > 0 ? (<div><Accordion title="Measurements" count={measurements.length} defaultOpen={true}>{renderNodeTable(measurements)}</Accordion><Accordion title="Digital Signals" count={digitalSignals.length}>{renderNodeTable(digitalSignals)}</Accordion><Accordion title="Commands" count={commands.length}>{renderNodeTable(commands)}</Accordion><Accordion title="User Commands" count={userCommands.length}>{renderNodeTable(userCommands, true)}</Accordion></div>) : (<div className="text-center p-8 bg-gray-50/50 rounded-md"><p className="text-sm text-gray-500 font-medium">{plc.error || (isConnected ? 'No nodes found.' : 'Waiting for connection...')}</p></div>)}</div>);
  });

  return (
    <div className="min-h-screen bg-gray-100 p-4 md:p-8 font-sans">
      <header className="mb-8 text-center relative">
        <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight mb-2">📊 Real-Time OPC UA Dashboard</h1>
        <p className="text-lg text-gray-600">Live data streaming from multiple PLCs</p>
        <button onClick={logout} className="absolute top-0 right-0 mt-2 mr-2 bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-md">Logout</button>
      </header>
      <div className="max-w-7xl mx-auto">
        <div className={`mb-6 p-4 rounded-lg shadow-sm border ${wsStatus === 'Connected' ? 'bg-blue-50 border-blue-300' : 'bg-red-50 border-red-300'}`}><p className="font-semibold text-base flex items-center"><span className={`w-3 h-3 rounded-full mr-3 ${wsStatus === 'Connected' ? 'bg-blue-500' : 'bg-red-500'}`}></span>WebSocket Status: {wsStatus}{wsStatus === 'Connected' && (<span className="ml-4 font-normal text-gray-700">| <span className="font-bold">{connectedPlcs}</span> / {plcData.length} PLCs Connected</span>)}</p></div>
        {plcData.length === 0 ? <LoadingSpinner /> : <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">{plcData.map(plc => <PlcCard key={plc.url} plc={plc} token={token} />)}</div>}
      </div>
    </div>
  );
};


// ===============================================
// 4. MAIN APP COMPONENT (Router)
// ===============================================
const App = () => {
    const { token } = useAuth();
    return token ? <DashboardPage /> : <LoginPage />;
};

// --- Wrap the App in the AuthProvider ---
const AppWrapper = () => (
    <AuthProvider>
        <App />
    </AuthProvider>
);

export default AppWrapper;

