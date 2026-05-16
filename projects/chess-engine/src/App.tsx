import { createSignal, createEffect, onMount, onCleanup, Show, For } from 'solid-js'
import { Chess, Move, SQUARES } from 'chess.js'

// Types
type Mode = 'play' | 'analysis'
type Color = 'white' | 'black'

interface GameState {
  game: Chess
  selectedSquare: string | null
  possibleMoves: string[]
  lastMove: { from: string; to: string } | null
  bestMove: { from: string; to: string } | null
  boardFlipped: boolean
  userColor: Color
  mode: Mode
  engineReady: boolean
  engineThinking: boolean
  analysisDepth: number
  fen: string
}

// Piece unicode
const PIECES: Record<string, string> = {
  'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
  'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
}

// Stockfish global
let stockfish: Worker | null = null

function initStockfish(): Promise<void> {
  return new Promise((resolve) => {
    stockfish = new Worker('/stockfish.js')
    
    const onMessage = (e: MessageEvent) => {
      const msg = e.data
      if (msg === 'readyok') {
        stockfish?.removeEventListener('message', onMessage)
        resolve()
      }
    }
    
    stockfish.addEventListener('message', onMessage)
    stockfish.postMessage('uci')
    
    // Fallback timeout
    setTimeout(() => {
      resolve()
    }, 3000)
  })
}

function App() {
  // Game state
  const [game, setGame] = createSignal(new Chess())
  const [selectedSquare, setSelectedSquare] = createSignal<string | null>(null)
  const [possibleMoves, setPossibleMoves] = createSignal<string[]>([])
  const [lastMove, setLastMove] = createSignal<{ from: string; to: string } | null>(null)
  const [bestMove, setBestMove] = createSignal<{ from: string; to: string } | null>(null)
  const [boardFlipped, setBoardFlipped] = createSignal(false)
  const [userColor, setUserColor] = createSignal<Color>('white')
  const [mode, setMode] = createSignal<Mode>('play')
  const [engineReady, setEngineReady] = createSignal(false)
  const [engineThinking, setEngineThinking] = createSignal(false)
  const [analysisDepth, setAnalysisDepth] = createSignal(0)

  // Engine callbacks
  let onEngineMove: ((from: string, to: string) => void) | null = null
  let onEngineDepth: ((depth: number) => void) | null = null

  onMount(async () => {
    await initStockfish()
    setEngineReady(true)
  })

  onCleanup(() => {
    stockfish?.terminate()
  })

  // Get squares in board order
  function getSquares(): string[] {
    const squares: string[] = []
    const files = boardFlipped() ? ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a'] : ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    const ranks = boardFlipped() ? ['1', '2', '3', '4', '5', '6', '7', '8'] : ['8', '7', '6', '5', '4', '3', '2', '1']
    
    for (const rank of ranks) {
      for (const file of files) {
        squares.push(file + rank)
      }
    }
    return squares
  }

  // Handle square click
  function handleSquareClick(square: string) {
    const g = game()
    const selected = selectedSquare()
    const moves = possibleMoves()

    // Analysis mode - free editing, any move allowed
    if (mode() === 'analysis') {
      if (selected) {
        // Try to make move (may be illegal)
        try {
          const move = g.move({ from: selected, to: square, promotion: 'q' })
          if (move) {
            setLastMove({ from: selected, to: square })
          }
        } catch {
          // Invalid move - try to place piece manually
        }
        setSelectedSquare(null)
        setPossibleMoves([])
      } else {
        // Select square
        setSelectedSquare(square)
        const validMoves = g.moves({ square, verbose: true }).map((m: Move) => m.to)
        setPossibleMoves(validMoves)
      }
      setGame(new Chess(g.fen()))
      analyzePosition()
      return
    }

    // Play mode - strict rules
    const turn = g.turn()
    const isUserTurn = (turn === 'w' && userColor() === 'white') || (turn === 'b' && userColor() === 'black')
    
    if (!isUserTurn) return

    if (selected) {
      // Try to make move
      const move = g.move({ from: selected, to: square, promotion: 'q' })
      if (move) {
        setLastMove({ from: selected, to: square })
        setSelectedSquare(null)
        setPossibleMoves([])
        setGame(new Chess(g.fen()))
        
        // Clear best move arrow after user moves
        setBestMove(null)
        
        // Get bot move
        if (!g.isGameOver()) {
          getBotMove()
        }
      } else {
        // Check if clicking on own piece
        const piece = g.get(square)
        if (piece && ((turn === 'w' && piece.color === 'w') || (turn === 'b' && piece.color === 'b'))) {
          setSelectedSquare(square)
          const validMoves = g.moves({ square, verbose: true }).map((m: Move) => m.to)
          setPossibleMoves(validMoves)
        } else {
          setSelectedSquare(null)
          setPossibleMoves([])
        }
      }
    } else {
      // Select piece
      const piece = g.get(square)
      if (piece && ((turn === 'w' && piece.color === 'w') || (turn === 'b' && piece.color === 'b'))) {
        setSelectedSquare(square)
        const validMoves = g.moves({ square, verbose: true }).map((m: Move) => m.to)
        setPossibleMoves(validMoves)
      }
    }
  }

  // Get bot move from Stockfish
  function getBotMove() {
    if (!stockfish) return
    
    const g = game()
    const fen = g.fen()
    
    setEngineThinking(true)
    
    let bestMoveFound = ''
    let depthReached = 0
    
    const handleMessage = (e: MessageEvent) => {
      const msg = e.data
      if (msg.startsWith('bestmove')) {
        const move = msg.split(' ')[1]
        if (move && move !== '(none)') {
          bestMoveFound = move
          if (move.length === 4 || move.length === 5) {
            const from = move.substring(0, 2)
            const to = move.substring(2, 4)
            setBestMove({ from, to })
            
            // Make the move
            try {
              g.move({ from, to, promotion: move.length === 5 ? move[4] as 'q'|'r'|'b'|'n' : 'q' })
              setLastMove({ from, to })
              setGame(new Chess(g.fen()))
            } catch {}
          }
        }
        setEngineThinking(false)
        stockfish?.removeEventListener('message', handleMessage)
      } else if (msg.startsWith('depth')) {
        const depth = parseInt(msg.split(' ')[1])
        depthReached = depth
        setAnalysisDepth(depth)
      }
    }
    
    stockfish.addEventListener('message', handleMessage)
    stockfish.postMessage(`position fen ${fen}`)
    stockfish.postMessage('go depth 20')
  }

  // Analyze position for best move (for analysis mode)
  function analyzePosition() {
    if (!stockfish) return
    
    const g = game()
    const fen = g.fen()
    
    setEngineThinking(true)
    setBestMove(null)
    
    let depthReached = 0
    
    const handleMessage = (e: MessageEvent) => {
      const msg = e.data
      if (msg.startsWith('bestmove')) {
        const move = msg.split(' ')[1]
        if (move && move !== '(none)' && move.length >= 4) {
          const from = move.substring(0, 2)
          const to = move.substring(2, 4)
          setBestMove({ from, to })
        }
        setEngineThinking(false)
        stockfish?.removeEventListener('message', handleMessage)
      } else if (msg.startsWith('depth')) {
        const depth = parseInt(msg.split(' ')[1])
        depthReached = depth
        setAnalysisDepth(depth)
      }
    }
    
    stockfish.addEventListener('message', handleMessage)
    stockfish.postMessage(`position fen ${fen}`)
    stockfish.postMessage('go depth 20')
  }

  // Reset game
  function resetGame() {
    setGame(new Chess())
    setSelectedSquare(null)
    setPossibleMoves([])
    setLastMove(null)
    setBestMove(null)
    setAnalysisDepth(0)
    
    // If playing as black, get bot move
    if (mode() === 'play' && userColor() === 'black' && !game().isGameOver()) {
      getBotMove()
    }
  }

  // Toggle flip
  function toggleFlip() {
    setBoardFlipped(!boardFlipped())
  }

  // Get arrow path for best move
  function getArrowPath(): string | null {
    const move = bestMove()
    if (!move) return null
    
    const fromFile = move.from.charCodeAt(0) - 97
    const fromRank = parseInt(move.from[1]) - 1
    const toFile = move.to.charCodeAt(0) - 97
    const toRank = parseInt(move.to[1]) - 1
    
    // Adjust for flipped board
    const adjFromFile = boardFlipped() ? 7 - fromFile : fromFile
    const adjFromRank = boardFlipped() ? fromRank : 7 - fromRank
    const adjToFile = boardFlipped() ? 7 - toFile : toFile
    const adjToRank = boardFlipped() ? toRank : 7 - toRank
    
    // Calculate center positions as percentages
    const x1 = (adjFromFile + 0.5) * 12.5
    const y1 = (adjFromRank + 0.5) * 12.5
    const x2 = (adjToFile + 0.5) * 12.5
    const y2 = (adjToRank + 0.5) * 12.5
    
    // Arrow parameters
    const dx = x2 - x1
    const dy = y2 - y1
    const len = Math.sqrt(dx * dx + dy * dy)
    const ux = dx / len
    const uy = dy / len
    
    // Shorten arrow to not overlap squares too much
    const shorten = 6
    const ax1 = x1 + ux * shorten
    const ay1 = y1 + uy * shorten
    const ax2 = x2 - ux * (shorten + 4)
    const ay2 = y2 - uy * (shorten + 4)
    
    // Arrow head
    const headLen = 4
    const headAngle = Math.PI / 6
    const angle = Math.atan2(ay2 - ay1, ax2 - ax1)
    
    const hx1 = ax2 - headLen * Math.cos(angle - headAngle)
    const hy1 = ay2 - headLen * Math.sin(angle - headAngle)
    const hx2 = ax2 - headLen * Math.cos(angle + headAngle)
    const hy2 = ay2 - headLen * Math.sin(angle + headAngle)
    
    return `M ${ax1}% ${ay1}% L ${ax2}% ${ay2}% M ${hx1}% ${hy1}% L ${ax2}% ${ay2}% L ${hx2}% ${hy2}%`
  }

  // Render square
  function renderSquare(square: string, index: number) {
    const g = game()
    const piece = g.get(square)
    const isSelected = selectedSquare() === square
    const isPossible = possibleMoves().includes(square)
    const isLastMove = lastMove()?.from === square || lastMove()?.to === square
    const isCheck = g.inCheck() && (() => {
      const board = g.board()
      for (let r = 0; r < 8; r++) {
        for (let f = 0; f < 8; f++) {
          const p = board[r]?.[f]
          if (p?.type === 'k' && p.color === g.turn()) {
            const sq = String.fromCharCode(97 + f) + (8 - r)
            return sq === square
          }
        }
      }
      return false
    })()
    
    const file = square.charCodeAt(0) - 97
    const rank = parseInt(square[1])
    const isLight = (file + rank) % 2 === 1
    
    let className = `square ${isLight ? 'light' : 'dark'}`
    if (isSelected) className += ' selected'
    if (isPossible) className += ' possible'
    if (isLastMove) className += ' last-move'
    if (isCheck) className += ' check'
    
    // Handle drag and drop for piece movement
    const handleDragStart = (e: React.DragEvent) => {
      if (!piece) return
      
      // Only allow dragging user's pieces in play mode
      if (mode() === 'play') {
        const turn = g.turn()
        const isUserTurn = (turn === 'w' && userColor() === 'white') || (turn === 'b' && userColor() === 'black')
        if (!isUserTurn) return
        
        const isUserPiece = (turn === 'w' && piece.color === 'w') || (turn === 'b' && piece.color === 'b')
        if (!isUserPiece) return
      }
      
      // Store the source square and piece info
      e.dataTransfer.setData('text/plain', square)
      e.dataTransfer.effectAllowed = 'move'
    }
    
    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
    }
    
    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault()
      const fromSquare = e.dataTransfer.getData('text/plain')
      const toSquare = square
      
      // Don't allow dropping on same square
      if (fromSquare === toSquare) return
      
      // Handle the move based on mode
      if (mode() === 'analysis') {
        // Analysis mode - free editing
        try {
          const move = g.move({ from: fromSquare, to: toSquare, promotion: 'q' })
          if (move) {
            setLastMove({ from: fromSquare, to: toSquare })
            setGame(new Chess(g.fen()))
            analyzePosition()
          }
        } catch (err) {
          // Invalid move - ignore
        }
      } else {
        // Play mode - strict rules
        const turn = g.turn()
        const isUserTurn = (turn === 'w' && userColor() === 'white') || (turn === 'b' && userColor() === 'black')
        if (!isUserTurn) return
        
        const fromPiece = g.get(fromSquare)
        const isUserPiece = (turn === 'w' && fromPiece?.color === 'w') || (turn === 'b' && fromPiece?.color === 'b')
        if (!isUserPiece) return
        
        // Try to make the move
        const move = g.move({ from: fromSquare, to: toSquare, promotion: 'q' })
        if (move) {
          setLastMove({ from: fromSquare, to: toSquare })
          setGame(new Chess(g.fen()))
          
          // Clear best move arrow after user moves
          setBestMove(null)
          
          // Get bot move if game not over
          if (!g.isGameOver()) {
            getBotMove()
          }
        }
        // If invalid move, do nothing (piece will snap back via drag events)
      }
    }
    
    const handleDragLeave = (e: React.DragEvent) => {
      // Clean up any drag-over styling if needed
    }
    
    return (
      <div 
        class={className} 
        onClick={() => handleSquareClick(square)}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDragLeave={handleDragLeave}
      >
        <Show when={piece}>
          <span 
            class={`piece ${piece.color === 'w' ? 'white' : 'black'}`} 
            draggable={true}
          >
            {PIECES[piece.type]}
          </span>
        </Show>
      </div>
    )
  }

  // Get status text
  function getStatus(): string {
    const g = game()
    if (g.isCheckmate()) return 'Checkmate!'
    if (g.isDraw()) return 'Draw'
    if (g.isThreefoldRepetition()) return 'Repetition'
    if (g.isInsufficientMaterial()) return 'Insufficient Material'
    if (g.isStalemate()) return 'Stalemate'
    return g.inCheck() ? 'Check!' : (g.turn() === 'w' ? 'White to move' : 'Black to move')
  }

  // Check game over
  function isGameOver(): boolean {
    return game().isGameOver()
  }

  return (
    <div class="app">
      <header class="header">
        <div class="logo">Chess Engine</div>
        
        <div class="mode-tabs">
          <button
            class={`mode-tab ${mode() === 'play' ? 'active' : ''}`}
            onClick={() => setMode('play')}
          >
            Play vs Bot
          </button>
          <button
            class={`mode-tab ${mode() === 'analysis' ? 'active' : ''}`}
            onClick={() => setMode('analysis')}
          >
            Analysis Board
          </button>
        </div>
        
        <div class="controls">
          <button class={`control-btn ${userColor() === 'white' ? 'active' : ''}`} onClick={() => setUserColor('white')}>
            White
          </button>
          <button class={`control-btn ${userColor() === 'black' ? 'active' : ''}`} onClick={() => setUserColor('black')}>
            Black
          </button>
        </div>
      </header>
      
      <main class="main">
        <div class="board-container">
          <div class="board">
            <For each={getSquares()}>
              {(square, index) => renderSquare(square, index())}
            </For>
            <Show when={bestMove()}>
              <svg class="arrow-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                <path class="arrow" d={getArrowPath() || ''} stroke="currentColor" stroke-width="2" fill="none" />
              </svg>
            </Show>
          </div>
          <button class="flip-btn" onClick={toggleFlip}>
            Flip Board
          </button>
        </div>
        
        <div class="sidebar">
          <div class="panel">
            <div class="panel-title">Game Status</div>
            <div class={`status ${game().turn() === 'w' ? 'turn-white' : 'turn-black'} ${game().inCheck() ? 'check' : ''}`}>
              {getStatus()}
            </div>
            
            <Show when={mode() === 'play'}>
              <div class="game-info" style="margin-top: 16px">
                <div class="info-row">
                  <span class="info-label">Playing as</span>
                  <span class="info-value">{userColor() === 'white' ? 'White' : 'Black'}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">Bot</span>
                  <span class="info-value">{userColor() === 'white' ? 'Black' : 'White'}</span>
                </div>
              </div>
            </Show>
          </div>
          
          <div class="panel">
            <div class="panel-title">Engine</div>
            <div class="engine-status">
              <div class={`engine-dot ${engineReady() ? 'ready' : ''} ${engineThinking() ? 'thinking' : ''}`}></div>
              <span>{engineReady() ? (engineThinking() ? 'Thinking...' : 'Ready') : 'Loading...'}</span>
            </div>
            
            <Show when={engineThinking()}>
              <div class="depth-indicator">
                <div class="depth-bar">
                  <div class="depth-fill" style={`width: ${Math.min(analysisDepth() / 20 * 100, 100)}%`}></div>
                </div>
                <span class="depth-text">d{analysisDepth()}</span>
              </div>
            </Show>
            
            <Show when={mode() === 'analysis'}>
              <div class="analysis-info" style="margin-top: 12px">
                <Show when={bestMove()}>
                  <div>Best move: <span style="color: var(--accent)">{bestMove()?.from} → {bestMove()?.to}</span></div>
                </Show>
                <Show when={!bestMove() && !engineThinking()}>
                  <div>Click a piece to see moves</div>
                </Show>
              </div>
            </Show>
          </div>
          
          <button class="action-btn" onClick={resetGame}>
            New Game
          </button>
        </div>
      </main>
    </div>
  )
}

export default App
