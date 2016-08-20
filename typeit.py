#!/usr/bin/env python
import curses
import time
import os
import sys
import glob
import re
import json
import random
import math


class Model:
    colors = [
        curses.COLOR_GREEN,
        curses.COLOR_WHITE,
        curses.COLOR_RED,
        curses.COLOR_MAGENTA,
        curses.COLOR_CYAN,
        curses.COLOR_BLUE,
        curses.COLOR_YELLOW,
    ]
    bgColor = curses.COLOR_BLACK
    (screenSizeY, screenSizeX) = (25, 80)
    scoreBoardStr = 'Typo: ---- Words: ---- Score: ----- WPM: --- Misses: --'
    hlineY = screenSizeY - 2
    vlineX = screenSizeX
    gameBoardY = screenSizeY - 2
    scoreBoardY = screenSizeY - 1
    scoreBoardX = screenSizeX - len(scoreBoardStr)
    scorePosX = [m.start()+scoreBoardX+2  for m in re.finditer(': ', scoreBoardStr)]
    scoreFormatStr = ['%-4d', '%-4d', '%-5d', '%-3d', '%-2d']
    (minMisses, maxMisses) = (0, 99)
    (minWordLen, maxWordLen) = (1, 19)
    (minWords, maxWords) = (1, 20)
    minStep = 1
    minSpeed = 1
    maxLevels = 11
    levelRatio = 100
    typorateThresholds = [0, 1, 3, 5, 7, 10, 14, 19, 29, 49]
    menuOffset = 5
    initialRate = 2.0
    maxHighScores = 10

    def __init__(self):
        self.exedir = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.wordsfiles = glob.glob(os.path.join(self.exedir, 'words', 'words.*'))
        self.rulesfile = os.path.join(self.exedir, 'rules.json')
        self.highscoresfile = os.path.join(self.exedir, 'highscores.json')
        self.loadRules()
        self.wordtypes = []
        wordsRegex = re.compile(r'words\.(.*)$')
        for file in self.wordsfiles:
            match = wordsRegex.search(file)
            self.wordtypes.append(match.group(1))
        self.highscores = HighScores(self.highscoresfile)

    def loadRules(self):
        fp = open(self.rulesfile, 'r')
        self.rules = json.load(fp)
        fp.close()
        self.__clipValues('misses', Model.minMisses, Model.maxMisses)
        self.__clipValues('min_word_length', Model.minWordLen, -1)
        self.__clipValues('max_word_length', -1, Model.maxWordLen)
        self.__clipValues('max_words', Model.minWords, Model.maxWords)
        self.__clipValues('min_speed', Model.minSpeed, -1)
        self.__clipValues('step', Model.minStep, -1)

    def __clipValues(self, key, mini=-1, maxi=-1):
        if self.rules[key] < mini  and  mini != -1:
            self.rules[key] = mini
        if self.rules[key] > maxi  and  maxi != -1:
            self.rules[key] = maxi

    def checkScreenDimension(self, dim):
        (dimy, dimx) = dim
        if dimy < Model.screenSizeY  or  dimx < Model.screenSizeX:
            raise Exception("You need a minimum screen size of '(%d,%d)'!" % (screenSizeY, screenSizeX))

    def loadWords(self, index):
        file = self.wordsfiles[index]
        fp = open(file, 'r')
        tmp = map(self.__strip, fp.readlines())
        fp.close()
        words = []
        for word in tmp:
            if len(word) >= self.rules['min_word_length']  and  len(word) <= self.rules['max_word_length']:
                words.append(word)
        return words

    def __strip(self, line):
        line = line.strip('\n')
        line = line.strip('\r')
        return line


class HighScores:
    def __init__(self, scoresFile):
        self.scoresFile = scoresFile
        if not os.path.exists(scoresFile):
            self.data = []
        else:
            fp = open(scoresFile, 'r')
            self.data = json.load(fp)
            fp.close()

    def saveScores(self):
        print self.data
        self.data = sorted(self.data, reverse=True, key=lambda (item): item[0])
        fp = open(self.scoresFile, 'w')
        num = min(Model.maxHighScores, len(self.data))
        fp.write('[\n')
        for idx in range(0,num):
            s = self.data[idx]
            fp.write('  [%d, %d, %d, %f, %f]' % (s[0], s[1], s[2], s[3], s[4]))
            if idx != num-1:
                fp.write(',')
            fp.write('\n')
        fp.write(']\n')
        fp.close()

    def addScore(self, score):
        self.data.append((score.score, score.wpm, score.wordswritten, score.duration, score.typos*100.0/score.wordswritten))


class Score:
    def __init__(self):
        self.score = 0
        self.wordswritten = 0
        self.wpm = 0
        self.typos = 0
        self.duration = 0
        self.starttime = time.time()
        self.misses = 0

    def updateTypo(self):
        self.typos += 1

    def updateMisses(self):
        self.misses += 1

    def updateScore(self, wordLen):
        self.score += wordLen
        self.wordswritten += 1
        self.updateWpm()

    def updateWpm(self):
        self.duration = time.time() - self.starttime
        self.wpm = self.wordswritten * 60.0 / self.duration

    def getLevel(self):
        if self.score < 0:
            self.score = 0
        level = math.ceil(self.score / Model.levelRatio)
        if level > Model.maxLevels:
            level = Model.maxLevels
        level = Model.maxLevels - level
        return level

    def typorank(self):
        for i in range(0, len(Model.typorateThresholds)):
            if self.typos <= Model.typorateThresholds[i]:
                return i
        return len(Model.typorateThresholds)+1


class View:
    def __init__(self, model):
        self.model = model
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.flushinp()
        self.stdscr.keypad(1)
        self.stdscr.nodelay(0)
        self.stdscr.clear()
        self.stdscr.refresh()
        self.model.checkScreenDimension(self.stdscr.getmaxyx())
        for i in range(0, len(Model.colors)):
            curses.init_pair(i+1, Model.colors[i], Model.bgColor)

    def refresh(self):
        self.stdscr.refresh()

    def clear(self):
        self.stdscr.clear()

    def pressAnyKey(self, y, x):
        self.stdscr.addstr(y, x, "Press any key to continue...")
        self.refresh()
        time.sleep(1)
        curses.flushinp()
        self.stdscr.getch()

    def clearWordAt(self, y, x, length):
        if length <= 0:
            return
        self.stdscr.addstr(y, x, ' '*length)

    def showWordAt(self, y, x, word):
        self.stdscr.addstr(y, x, word)

    def setNonBlockingInput(self):
        self.stdscr.nodelay(1)

    def setBlockingInput(self):
        self.stdscr.nodelay(0)

    def drawGameScreen(self):
        self.stdscr.hline(Model.hlineY, 0, curses.ACS_HLINE, Model.screenSizeX)
        self.stdscr.vline(0, Model.vlineX, curses.ACS_VLINE, Model.screenSizeY)
        self.stdscr.addstr(Model.scoreBoardY, Model.scoreBoardX, Model.scoreBoardStr)
        self.stdscr.move(Model.scoreBoardY, 0)

    def drawScores(self, score):
        self.stdscr.addstr(Model.scoreBoardY, Model.scorePosX[0], Model.scoreFormatStr[0] % score.typos)
        self.stdscr.addstr(Model.scoreBoardY, Model.scorePosX[1], Model.scoreFormatStr[1] % score.wordswritten)
        self.stdscr.addstr(Model.scoreBoardY, Model.scorePosX[2], Model.scoreFormatStr[2] % score.score)
        self.stdscr.addstr(Model.scoreBoardY, Model.scorePosX[3], Model.scoreFormatStr[3] % score.wpm)
        self.stdscr.addstr(Model.scoreBoardY, Model.scorePosX[4], Model.scoreFormatStr[4] % score.misses)

    def showMenu(self, title, choices):
        pointer = 0
        self.stdscr.clear()
        self.stdscr.addstr(Model.menuOffset-2, Model.menuOffset, "Choose using UP/DOWN, any other key to confirm...")
        self.stdscr.addstr(Model.menuOffset-1, Model.menuOffset, title)
        while True:
            for i in range(0,len(choices)):
                if pointer == i:
                    self.stdscr.addstr(i+Model.menuOffset, Model.menuOffset, "-> %s" % choices[i])
                else:
                    self.stdscr.addstr(i+Model.menuOffset, Model.menuOffset, "   %s" % choices[i])
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch == curses.KEY_UP:
                pointer -= 1
                if pointer < 0:
                    pointer = len(choices) - 1
            elif ch == curses.KEY_DOWN:
                pointer += 1
                if pointer >= len(choices):
                    pointer = 0
            else:
                return pointer

    def __del__(self):
        self.stdscr.nodelay(0)
        self.stdscr.keypad(0)
        curses.flushinp()
        curses.nocbreak()
        curses.echo()
        self.stdscr.clear()
        self.stdscr.refresh()
        curses.endwin()


class Words:
    def __init__(self, rules, wordsList):
        self.minspeed = rules['min_speed']
        self.maxspeed = rules['max_speed']
        self.maxwords = rules['max_words']
        self.step = rules['step']
        self.rate = 1
        self.wordsList = wordsList
        self.wordPosLimit = len(self.wordsList) - 1
        self.currWordsLen = 0
        self.currWords = []
        self.currYpos = 0
        self.currWordTyped = ''

    def addCurrentChar(self, ch, view):
        self.currWordTyped += ch
        self.addTypedWord(view)

    def removeChar(self, view):
        view.clearWordAt(Model.scoreBoardY, 0, len(self.currWordTyped))
        self.currWordTyped = self.currWordTyped[:-1]
        self.addTypedWord(view)

    def addTypedWord(self, view):
        view.stdscr.addstr(Model.scoreBoardY, 0, self.currWordTyped)
        view.refresh()

    def chooseNextWordAndUpdateRate(self, score, view):
        if len(self.currWords) < self.maxwords:
            yPos = self.currYpos
            # TODO: selection without replacement
            # TODO: random yPos?
            word = self.wordsList[random.randint(0, self.wordPosLimit)]
            self.currYpos += 1
            if self.currYpos >= Model.gameBoardY:
                self.currYpos = 0
            self.currWordsLen += len(word)
            self.currWords.append([yPos, 0, word])
            view.showWordAt(yPos, 0, word)
        self.rate = float(score.score) / self.step + self.minspeed
        if self.maxspeed > 0  and  self.rate > self.maxspeed:
            self.rate = self.maxspeed

    def moveWords(self, view):
        for i in range(0,len(self.currWords)):
            (y, x, w) = self.currWords[i]
            view.clearWordAt(y, x, len(w))
            view.showWordAt(y, x+1, w)
            self.currWords[i][1] += 1

    def removeMatchedWordAndUpdateScore(self, score, view):
        word = self.currWordTyped
        length = len(self.currWordTyped)
        self.currWordTyped = ''
        for i in range(0,len(self.currWords)):
            (y, x, w) = self.currWords[i]
            if w != word:
                continue
            score.updateScore(len(w))
            view.clearWordAt(y, x, len(w))
            self.currWordsLen -= len(w)
            del self.currWords[i]
            view.clearWordAt(Model.scoreBoardY, 0, length)
            self.addTypedWord(view)
            return
        view.clearWordAt(Model.scoreBoardY, 0, length)
        score.updateTypo()

    def removeTimedOutWordAndUpdateScore(self, score, view):
        tmp = []
        for i in range(0,len(self.currWords)):
            (y, x, w) = self.currWords[i]
            xend = x + len(w)
            if xend < Model.screenSizeX:
                tmp.append([y, x, w])
                continue
            wlen = len(w)
            score.updateMisses()
            self.currWordsLen -= wlen
            view.clearWordAt(y, x, len(w))
        self.currWords = tmp


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        random.seed(int(time.time()))

    def showMainMenu(self):
        items = ["Test your speed",  "Options [TODO]",  "HighScores", "Quit"]
        while True:
            index = self.view.showMenu('Typeit!', items)
            if index == 1:
                #TODO: show options page
                break
            if index == 2:
                self.showHighScores()
            elif index == 3:
                break
            else:
                self.showWordsMenu()
        self.model.highscores.saveScores()

    def showHighScores(self):
        self.view.clear()
        num = min(Model.maxHighScores, len(self.model.highscores.data))
        self.view.stdscr.addstr(1, 10, "Top %d Scores" % num)
        self.view.stdscr.addstr(2, 0, "Idx.  Score  WPM  Words  Time(s)  Typo%")
        for idx in range(0,num):
            s = self.model.highscores.data[idx]
            tmp = "%4d  %5d  %3d  %5d  %4.2f  %3.2f" % (idx+1, s[0], s[1], s[2], s[3], s[4])
            self.view.stdscr.addstr(idx+3, 0, tmp)
        self.view.pressAnyKey(0, 15)

    def showWordsMenu(self):
        while True:
            words = self.getIndexAndLoadWords()
            if len(words) != 0:
                self.playGame(words)
            else:
                break

    def parseInput(self, words, score):
        ch = self.view.stdscr.getch()
        if ch < 0:
            return
        if ch >= 0 and ch <= 127:
            char = chr(ch)
        else:
            char = ''
        if ch == curses.KEY_END:
            return True
        if char == '\n'  or  char == '\r'  or  char == ' ':
            words.removeMatchedWordAndUpdateScore(score, self.view)
        elif ch == curses.KEY_BACKSPACE:
            words.removeChar(self.view)
        else:
            words.addCurrentChar(char, self.view)
        return False

    def playGame(self, wordsList):
        score = Score()
        words = Words(self.model.rules, wordsList)
        self.view.clear()
        self.view.drawGameScreen()
        self.view.setNonBlockingInput()
        oldtime = time.time()
        endGame = False
        while score.misses < self.model.rules['misses']:
            self.view.drawScores(score)
            words.removeTimedOutWordAndUpdateScore(score, self.view)
            words.chooseNextWordAndUpdateRate(score, self.view)
            words.moveWords(self.view)
            words.addTypedWord(self.view)
            while time.time() < oldtime + (Model.initialRate / words.rate):
                if self.parseInput(words, score):
                    endGame = True
                    break
            if endGame:
                break
            oldtime = time.time()
        score.updateWpm()
        self.model.highscores.addScore(score)
        self.view.stdscr.addstr(13, 30, "GAME OVER!!")
        self.view.refresh()
        self.view.setBlockingInput()
        time.sleep(1)
        self.showScore(score)

    def showScore(self, score):
        self.view.clear()
        self.view.stdscr.addstr(11, 30, "Typeit Score...")
        self.view.stdscr.addstr(12, 30, "Typo %%: %.2f" % (score.typos * 100.0 / score.wordswritten))
        self.view.stdscr.addstr(13, 30, "Score : %d" % score.score)
        self.view.stdscr.addstr(14, 30, "WPM   : %d" % score.wpm)
        self.view.stdscr.addstr(15, 30, "Words : %d" % score.wordswritten)
        self.view.pressAnyKey(16, 30)

    def getIndexAndLoadWords(self):
        types = []
        types.extend(self.model.wordtypes)
        types.append('Go Back')
        index = self.view.showMenu('Select the words types from the list below', types)
        if index >= len(self.model.wordtypes):
            return []
        return self.model.loadWords(index)


def main():
    try:
        model = Model()
        view = View(model)
        controller = Controller(model, view)
        controller.showMainMenu()
    except:
        curses.endwin()
        raise

if __name__ == '__main__':
    main()
