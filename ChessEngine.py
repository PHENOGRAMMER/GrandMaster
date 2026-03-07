import random


class GameState:
    def __init__(self):
        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]
        ]
        self.moveLog = []
        self.whiteToMove = True
        self.whiteKingLocation = (7, 4)
        self.blackKingLocation = (0, 4)
        self.checkMate = False
        self.staleMate = False
        self.enPassantPossible = ()
        self.enPassantPossibleLog = [self.enPassantPossible]
        self.castleRights = CastleRights(True, True, True, True)
        self.castleRightsLog = [CastleRights(self.castleRights.wks, self.castleRights.wqs,
                                             self.castleRights.bks, self.castleRights.bqs)]
        self.halfMoveClock = 0
        self.halfMoveClockLog = [self.halfMoveClock]
        self.positionLog = [] # for threefold repetition

    def makeMove(self, move):
        self.board[move.startRow][move.startCol] = "--"
        promotedPiece = move.pieceMoved[0] + move.promotionChoice if move.isPawnPromotion else move.pieceMoved
        self.board[move.endRow][move.endCol] = promotedPiece
        self.moveLog.append(move)
        self.whiteToMove = not self.whiteToMove

        if move.pieceMoved == 'wK':
            self.whiteKingLocation = (move.endRow, move.endCol)
        elif move.pieceMoved == 'bK':
            self.blackKingLocation = (move.endRow, move.endCol)

        if move.isEnPassantMove:
            self.board[move.startRow][move.endCol] = "--"

        if move.pieceMoved[1] == 'p' and abs(move.startRow - move.endRow) == 2:
            self.enPassantPossible = ((move.startRow + move.endRow) // 2, move.endCol)
        else:
            self.enPassantPossible = ()

        if move.isCastleMove:
            if move.endCol - move.startCol == 2:
                self.board[move.endRow][move.endCol - 1] = self.board[move.endRow][move.endCol + 1]
                self.board[move.endRow][move.endCol + 1] = '--'
            else:
                self.board[move.endRow][move.endCol + 1] = self.board[move.endRow][move.endCol - 2]
                self.board[move.endRow][move.endCol - 2] = '--'

        self.enPassantPossibleLog.append(self.enPassantPossible)
        self.updateCastleRights(move)
        self.castleRightsLog.append(CastleRights(self.castleRights.wks, self.castleRights.wqs,
                                                 self.castleRights.bks, self.castleRights.bqs))
        
        # 50-move rule: reset on pawn move or capture
        if move.pieceMoved[1] == 'p' or move.pieceCaptured != '--':
            self.halfMoveClock = 0
        else:
            self.halfMoveClock += 1
        self.halfMoveClockLog.append(self.halfMoveClock)
        
        # Track position for 3-fold repetition
        self.positionLog.append(self.getBoardString())

    def undoMove(self):
        if not self.moveLog:
            return
        move = self.moveLog.pop()
        self.board[move.startRow][move.startCol] = move.pieceMoved
        self.board[move.endRow][move.endCol] = move.pieceCaptured
        self.whiteToMove = not self.whiteToMove

        if move.pieceMoved == 'wK':
            self.whiteKingLocation = (move.startRow, move.startCol)
        elif move.pieceMoved == 'bK':
            self.blackKingLocation = (move.startRow, move.startCol)

        if move.isEnPassantMove:
            self.board[move.endRow][move.endCol] = "--"
            self.board[move.startRow][move.endCol] = move.pieceCaptured

        self.enPassantPossibleLog.pop()
        self.enPassantPossible = self.enPassantPossibleLog[-1]

        self.castleRightsLog.pop()
        self.castleRights = self.castleRightsLog[-1]
        
        self.halfMoveClockLog.pop()
        self.halfMoveClock = self.halfMoveClockLog[-1]
        self.positionLog.pop()

        if move.isCastleMove:
            if move.endCol - move.startCol == 2:
                self.board[move.endRow][move.endCol + 1] = self.board[move.endRow][move.endCol - 1]
                self.board[move.endRow][move.endCol - 1] = '--'
            else:
                self.board[move.endRow][move.endCol - 2] = self.board[move.endRow][move.endCol + 1]
                self.board[move.endRow][move.endCol + 1] = '--'

        self.checkMate = False
        self.staleMate = False

    def getBoardString(self):
        """String representation for 3-fold rep check (includes turn and castle rights)"""
        return str(self.board) + str(self.whiteToMove) + str(self.castleRights.wks) + \
               str(self.castleRights.wqs) + str(self.castleRights.bks) + str(self.castleRights.bqs) + \
               str(self.enPassantPossible)

    def isDraw(self):
        if self.staleMate: return True, "Stalemate"
        if self.halfMoveClock >= 100: return True, "50-move rule"
        if self.isThreefoldRepetition(): return True, "Three-fold repetition"
        if self.isInsufficientMaterial(): return True, "Insufficient material"
        return False, ""

    def isThreefoldRepetition(self):
        if not self.positionLog: return False
        current = self.positionLog[-1]
        return self.positionLog.count(current) >= 3

    def isInsufficientMaterial(self):
        pieces = []
        for row in self.board:
            for sq in row:
                if sq != "--":
                    pieces.append(sq)
        
        if len(pieces) == 2: # King vs King
            return True
        if len(pieces) == 3: # King vs King + Knight/Bishop
            for p in pieces:
                if p[1] in ['N', 'B']:
                    return True
        if len(pieces) == 4: # King + Bishop vs King + Bishop (same color squares)
            # This is a bit more complex, for now we simplify to False for 4 pieces
            # unless we checking square colors.
            pass
        return False

    def getAllPossibleMoves(self):
        moves = []
        for r in range(len(self.board)):
            for c in range(len(self.board[r])):
                turn = self.board[r][c][0]
                if (turn == 'w' and self.whiteToMove) or (turn == 'b' and not self.whiteToMove):
                    piece = self.board[r][c][1]
                    if piece in self.moveFunctions:
                        self.moveFunctions[piece](self, r, c, moves)
        return moves

    def updateCastleRights(self, move):
        if move.pieceMoved == 'wK':
            self.castleRights.wks = False
            self.castleRights.wqs = False
        elif move.pieceMoved == 'bK':
            self.castleRights.bks = False
            self.castleRights.bqs = False
        elif move.pieceMoved == 'wR':
            if move.startRow == 7:
                if move.startCol == 0:
                    self.castleRights.wqs = False
                elif move.startCol == 7:
                    self.castleRights.wks = False
        elif move.pieceMoved == 'bR':
            if move.startRow == 0:
                if move.startCol == 0:
                    self.castleRights.bqs = False
                elif move.startCol == 7:
                    self.castleRights.bks = False

        if move.pieceCaptured == 'wR':
            if move.endRow == 7:
                if move.endCol == 0:
                    self.castleRights.wqs = False
                elif move.endCol == 7:
                    self.castleRights.wks = False
        elif move.pieceCaptured == 'bR':
            if move.endRow == 0:
                if move.endCol == 0:
                    self.castleRights.bqs = False
                elif move.endCol == 7:
                    self.castleRights.bks = False

    def getValidMoves(self):
        tempEnPassantPossible = self.enPassantPossible
        tempCastleRights = CastleRights(self.castleRights.wks, self.castleRights.wqs,
                                        self.castleRights.bks, self.castleRights.bqs)

        moves = self.getAllPossibleMoves()
        if self.whiteToMove:
            self.getCastleMoves(self.whiteKingLocation[0], self.whiteKingLocation[1], moves)
        else:
            self.getCastleMoves(self.blackKingLocation[0], self.blackKingLocation[1], moves)

        for i in range(len(moves) - 1, -1, -1):
            self.makeMove(moves[i])
            self.whiteToMove = not self.whiteToMove
            if self.inCheck():
                moves.remove(moves[i])
            self.whiteToMove = not self.whiteToMove
            self.undoMove()

        if len(moves) == 0:
            if self.inCheck():
                self.checkMate = True
            else:
                self.staleMate = True
        else:
            self.checkMate = False
            self.staleMate = False

        self.enPassantPossible = tempEnPassantPossible
        self.castleRights = tempCastleRights
        return moves

    def inCheck(self):
        if self.whiteToMove:
            return self.squareUnderAttack(self.whiteKingLocation[0], self.whiteKingLocation[1])
        else:
            return self.squareUnderAttack(self.blackKingLocation[0], self.blackKingLocation[1])

    def squareUnderAttack(self, r, c):
        self.whiteToMove = not self.whiteToMove
        oppMoves = self.getAllPossibleMoves()
        self.whiteToMove = not self.whiteToMove
        for move in oppMoves:
            if move.endRow == r and move.endCol == c:
                return True
        return False

    def getPawnMoves(self, r, c, moves):
        if self.whiteToMove:
            if r - 1 >= 0 and self.board[r - 1][c] == "--":
                if r - 1 == 0:
                    for promo in ['Q', 'R', 'B', 'N']:
                        moves.append(Move((r, c), (r - 1, c), self.board, promotionChoice=promo))
                else:
                    moves.append(Move((r, c), (r - 1, c), self.board))
                    if r == 6 and self.board[r - 2][c] == "--":
                        moves.append(Move((r, c), (r - 2, c), self.board))

            if r - 1 >= 0 and c - 1 >= 0:
                if self.board[r - 1][c - 1][0] == 'b':
                    if r - 1 == 0:
                        for promo in ['Q', 'R', 'B', 'N']:
                            moves.append(Move((r, c), (r - 1, c - 1), self.board, promotionChoice=promo))
                    else:
                        moves.append(Move((r, c), (r - 1, c - 1), self.board))
                elif (r - 1, c - 1) == self.enPassantPossible:
                    moves.append(Move((r, c), (r - 1, c - 1), self.board, isEnPassantMove=True))

            if r - 1 >= 0 and c + 1 <= 7:
                if self.board[r - 1][c + 1][0] == 'b':
                    if r - 1 == 0:
                        for promo in ['Q', 'R', 'B', 'N']:
                            moves.append(Move((r, c), (r - 1, c + 1), self.board, promotionChoice=promo))
                    else:
                        moves.append(Move((r, c), (r - 1, c + 1), self.board))
                elif (r - 1, c + 1) == self.enPassantPossible:
                    moves.append(Move((r, c), (r - 1, c + 1), self.board, isEnPassantMove=True))

        else:
            if r + 1 <= 7 and self.board[r + 1][c] == "--":
                if r + 1 == 7:
                    for promo in ['Q', 'R', 'B', 'N']:
                        moves.append(Move((r, c), (r + 1, c), self.board, promotionChoice=promo))
                else:
                    moves.append(Move((r, c), (r + 1, c), self.board))
                    if r == 1 and self.board[r + 2][c] == "--":
                        moves.append(Move((r, c), (r + 2, c), self.board))

            if r + 1 <= 7 and c - 1 >= 0:
                if self.board[r + 1][c - 1][0] == 'w':
                    if r + 1 == 7:
                        for promo in ['Q', 'R', 'B', 'N']:
                            moves.append(Move((r, c), (r + 1, c - 1), self.board, promotionChoice=promo))
                    else:
                        moves.append(Move((r, c), (r + 1, c - 1), self.board))
                elif (r + 1, c - 1) == self.enPassantPossible:
                    moves.append(Move((r, c), (r + 1, c - 1), self.board, isEnPassantMove=True))

            if r + 1 <= 7 and c + 1 <= 7:
                if self.board[r + 1][c + 1][0] == 'w':
                    if r + 1 == 7:
                        for promo in ['Q', 'R', 'B', 'N']:
                            moves.append(Move((r, c), (r + 1, c + 1), self.board, promotionChoice=promo))
                    else:
                        moves.append(Move((r, c), (r + 1, c + 1), self.board))
                elif (r + 1, c + 1) == self.enPassantPossible:
                    moves.append(Move((r, c), (r + 1, c + 1), self.board, isEnPassantMove=True))

    def getRookMoves(self, r, c, moves):
        directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
        enemy = 'b' if self.whiteToMove else 'w'
        for d in directions:
            for i in range(1, 8):
                endRow = r + d[0] * i
                endCol = c + d[1] * i
                if 0 <= endRow < 8 and 0 <= endCol < 8:
                    endPiece = self.board[endRow][endCol]
                    if endPiece == "--":
                        moves.append(Move((r, c), (endRow, endCol), self.board))
                    elif endPiece[0] == enemy:
                        moves.append(Move((r, c), (endRow, endCol), self.board))
                        break
                    else:
                        break
                else:
                    break

    def getKnightMoves(self, r, c, moves):
        knightMoves = ((-2, -1), (-1, -2), (-2, 1), (-1, 2),
                       (1, -2), (2, -1), (1, 2), (2, 1))
        ally = 'w' if self.whiteToMove else 'b'
        for m in knightMoves:
            endRow = r + m[0]
            endCol = c + m[1]
            if 0 <= endRow < 8 and 0 <= endCol < 8:
                endPiece = self.board[endRow][endCol]
                if endPiece[0] != ally:
                    moves.append(Move((r, c), (endRow, endCol), self.board))

    def getBishopMoves(self, r, c, moves):
        directions = ((-1, -1), (-1, 1), (1, -1), (1, 1))
        enemy = 'b' if self.whiteToMove else 'w'
        for d in directions:
            for i in range(1, 8):
                endRow = r + d[0] * i
                endCol = c + d[1] * i
                if 0 <= endRow < 8 and 0 <= endCol < 8:
                    endPiece = self.board[endRow][endCol]
                    if endPiece == "--":
                        moves.append(Move((r, c), (endRow, endCol), self.board))
                    elif endPiece[0] == enemy:
                        moves.append(Move((r, c), (endRow, endCol), self.board))
                        break
                    else:
                        break
                else:
                    break

    def getQueenMoves(self, r, c, moves):
        self.getRookMoves(r, c, moves)
        self.getBishopMoves(r, c, moves)

    def getKingMoves(self, r, c, moves):
        kingMoves = ((-1, -1), (-1, 0), (-1, 1),
                     (0, -1), (0, 1),
                     (1, -1), (1, 0), (1, 1))
        ally = 'w' if self.whiteToMove else 'b'
        for m in kingMoves:
            endRow = r + m[0]
            endCol = c + m[1]
            if 0 <= endRow < 8 and 0 <= endCol < 8:
                endPiece = self.board[endRow][endCol]
                if endPiece[0] != ally:
                    moves.append(Move((r, c), (endRow, endCol), self.board))

    def getCastleMoves(self, r, c, moves):
        if self.squareUnderAttack(r, c):
            return
        if (self.whiteToMove and self.castleRights.wks) or (not self.whiteToMove and self.castleRights.bks):
            self.getKingsideCastleMoves(r, c, moves)
        if (self.whiteToMove and self.castleRights.wqs) or (not self.whiteToMove and self.castleRights.bqs):
            self.getQueensideCastleMoves(r, c, moves)

    def getKingsideCastleMoves(self, r, c, moves):
        if self.board[r][c + 1] == '--' and self.board[r][c + 2] == '--':
            if not self.squareUnderAttack(r, c + 1) and not self.squareUnderAttack(r, c + 2):
                moves.append(Move((r, c), (r, c + 2), self.board, isCastleMove=True))

    def getQueensideCastleMoves(self, r, c, moves):
        if self.board[r][c - 1] == '--' and self.board[r][c - 2] == '--' and self.board[r][c - 3] == '--':
            if not self.squareUnderAttack(r, c - 1) and not self.squareUnderAttack(r, c - 2):
                moves.append(Move((r, c), (r, c - 2), self.board, isCastleMove=True))

    moveFunctions = {
        'p': getPawnMoves,
        'R': getRookMoves,
        'N': getKnightMoves,
        'B': getBishopMoves,
        'Q': getQueenMoves,
        'K': getKingMoves
    }


class CastleRights:
    def __init__(self, wks, wqs, bks, bqs):
        self.wks = wks
        self.wqs = wqs
        self.bks = bks
        self.bqs = bqs


class Move:
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}

    def __init__(self, startSq, endSq, board, isEnPassantMove=False, isCastleMove=False, promotionChoice=None):
        self.startRow = startSq[0]
        self.startCol = startSq[1]
        self.endRow = endSq[0]
        self.endCol = endSq[1]
        self.pieceMoved = board[self.startRow][self.startCol]
        self.pieceCaptured = board[self.endRow][self.endCol]
        self.isPawnPromotion = (self.pieceMoved == 'wp' and self.endRow == 0) or (
                    self.pieceMoved == 'bp' and self.endRow == 7)
        self.isEnPassantMove = isEnPassantMove
        if self.isEnPassantMove:
            self.pieceCaptured = 'wp' if self.pieceMoved == 'bp' else 'bp'
        self.isCastleMove = isCastleMove
        self.promotionChoice = promotionChoice if promotionChoice else 'Q'
        self.moveID = (self.startRow * 1000 + self.startCol * 100 + self.endRow * 10 + self.endCol)

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        if self.isPawnPromotion or other.isPawnPromotion:
            return self.moveID == other.moveID and self.promotionChoice == other.promotionChoice
        return self.moveID == other.moveID

    def __str__(self):
        return f"{self.pieceMoved} from {self.getRankFile(self.startRow, self.startCol)} to {self.getRankFile(self.endRow, self.endCol)}"

    def getChessNotation(self):
        """Returns UCI notation (e2e4)"""
        notation = self.getRankFile(self.startRow, self.startCol) + self.getRankFile(self.endRow, self.endCol)
        if self.isPawnPromotion:
            notation += self.promotionChoice.lower()
        return notation

    def getSAN(self, gs, moveIndex):
        """
        Returns Standard Algebraic Notation (SAN)
        Examples: e4, Nf3, Qxd5+, O-O, e8=Q#
        """
        # Castling
        if self.isCastleMove:
            if self.endCol - self.startCol == 2:
                return "O-O"
            else:
                return "O-O-O"

        pieceType = self.pieceMoved[1]
        notation = ""

        # Piece letter (nothing for pawns)
        if pieceType != 'p':
            notation += pieceType.upper()

        # Disambiguation (if multiple pieces of same type can move to same square)
        # This is simplified - full implementation would check all valid moves

        # Capture notation
        if self.pieceCaptured != "--" or self.isEnPassantMove:
            if pieceType == 'p':
                # For pawn captures, include the file
                notation += self.colsToFiles[self.startCol]
            notation += "x"

        # Destination square
        notation += self.getRankFile(self.endRow, self.endCol)

        # Promotion
        if self.isPawnPromotion:
            notation += "=" + self.promotionChoice

        # Check/Checkmate symbols would require checking game state after move
        # For now, we'll add them based on the game state
        # This would need to be called after the move is made

        return notation

    def getRankFile(self, r, c):
        return self.colsToFiles[c] + self.rowsToRanks[r]