// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import ".."

Item {
    id: cinema
    objectName: "launcherCinema"
    // Sem nome explícito o AT-SPI não oferecia como achar a cena Cinema.
    Accessible.role: Accessible.Pane
    Accessible.name: qsTr("Cinema")
    Accessible.description: qsTr("Cena do Launcher com a coleção e o jogo selecionado")
    property var scene: null
    property string currentFocus: ""
    readonly property bool selectionReady: scene !== null && scene.focusId === currentFocus
    readonly property var selectedGame: selectionReady && scene && scene.items ? scene.items[Number(scene.selected || 0)] || ({}) : ({})
    property var accessibility: ({})
    readonly property var activeLayout: scene && scene.layouts
        ? scene.layouts[String(scene.layoutId || "covers")] || scene.layouts.covers || ({})
        : ({})
    readonly property bool nativeRecipeLayout: ["wheel", "carousel", "stack"].indexOf(String(activeLayout.kind || "")) >= 0
        || (entries.length > 0 && entries[0].recipe !== undefined)
    readonly property var entries: activeLayout && activeLayout.entries
        && typeof activeLayout.entries.length === "number" ? activeLayout.entries : []
    readonly property real textScale: Math.max(1, Number(accessibility.visualScale || 1))
    readonly property var activeTheme: scene && scene.theme ? scene.theme : ({})
    readonly property var compiledThemeScene: activeTheme && activeTheme.compiledScene
        ? activeTheme.compiledScene : null
    readonly property var externalViewData: _externalView(compiledThemeScene)
    readonly property bool externalSceneAvailable: externalViewData !== null
        && Array.isArray(externalViewData.elements)
    readonly property var themeTokens: activeTheme && activeTheme.resolved
        ? activeTheme.resolved : ({})
    readonly property var themeColors: themeTokens.color || ({})
    readonly property var themeEffects: activeTheme && activeTheme.effects
        ? activeTheme.effects : ({})
    readonly property bool highContrast: !!accessibility.highContrast
        || activeTheme.highContrast === true
    readonly property bool reducedMotion: !!accessibility.reducedMotion
        || activeTheme.reducedMotion === true
    // A cena pode publicar o tier escolhido pelo Theme Engine. Até que o
    // contrato do catálogo publique a preferência, balanced é o fallback
    // seguro: mantém profundidade sem depender de vídeo ou shader externo.
    readonly property string performanceTier: scene && scene.performanceTier
        ? String(scene.performanceTier) : String(themeTokens.performance
            && themeTokens.performance.defaultTier || "balanced")
    readonly property bool backdropEffects: !highContrast && performanceTier !== "low"
    readonly property var selectedPalette: selectedGame && selectedGame.palette
        && typeof selectedGame.palette === "object" ? selectedGame.palette : ({})
    readonly property color accentColor: highContrast ? "#55d8ff"
        : _safeColor(String(themeColors.accent || selectedPalette.accent
                            || selectedPalette.vibrant || ""), "#22d3ee")
    readonly property color sceneBackgroundColor: highContrast ? "#000000"
        : _safeColor(String(themeColors.background || ""), "#071019")
    readonly property color primaryTextColor: highContrast ? "#ffffff"
        : _safeColor(String(themeColors.text || ""), "#f2f6fb")
    readonly property color mutedTextColor: highContrast ? "#e8e8e8"
        : _safeColor(String(themeColors.textMuted || ""), "#c3ced7")
    readonly property int motionDuration: reducedMotion ? 0
        : Math.max(0, Math.min(1000, Number(themeTokens.motion
            && themeTokens.motion.durationNormal || 180)))
    readonly property var contextualEffectStack: {
        if (highContrast || reducedMotion)
            return []
        const declared = themeEffects.contextualBackdrop
        if (Array.isArray(declared))
            return declared
        return performanceTier === "cinematic" ? [
            {"type": "blur", "parameters": {"radius": 28}},
            {"type": "vignette", "parameters": {"color": "#02060b", "strength": 0.72}}
        ] : []
    }
    readonly property var focusedCoverEffectStack: highContrast ? []
        : (Array.isArray(themeEffects.focusedCover) ? themeEffects.focusedCover : [])
    readonly property var peripheralCoverEffectStack: highContrast ? []
        : (Array.isArray(themeEffects.peripheralCover) ? themeEffects.peripheralCover : [])
    readonly property string videoSource: visible && selectionReady && performanceTier === "cinematic"
        ? String(selectedGame.videoUrl || "") : ""
    readonly property string connectionState: scene && scene.connectionState
        ? String(scene.connectionState) : "connected"
    readonly property string mediaPlaybackState: videoSource === "" ? "idle"
        : highContrast || reducedMotion ? "suppressed"
        : videoBackdrop.player !== null ? String(videoBackdrop.player.playbackState)
        : videoBackdrop.loadError !== "" ? "unavailable" : "loading"
    readonly property string mediaDiagnostic: videoBackdrop.player !== null
        ? String(videoBackdrop.player.errorMessage || videoBackdrop.player.audioDiagnostic || "")
        : videoBackdrop.loadError
    readonly property int decodedVideoFrames: videoBackdrop.player !== null
        ? Number(videoBackdrop.player.decodedFrames || 0) : 0
    readonly property string mediaSelectionKey: videoBackdrop.player !== null
        ? String(videoBackdrop.player.selectionKey || "") : ""
    property int clockTick: 0
    readonly property string clockLabel: {
        clockTick;
        return Qt.formatTime(new Date(), "hh:mm");
    }
    readonly property var metadataParts: {
        const game = cinema.selectedGame;
        const parts = [];
        if (game.releaseDate)
            parts.push(String(game.releaseDate).slice(0, 4));
        if (game.genres && game.genres.length)
            parts.push(game.genres.slice(0, 2).join(" / "));
        if (game.players !== undefined)
            parts.push(qsTr("%1 jogador(es)").arg(game.players));
        if (game.rating !== undefined)
            parts.push(qsTr("★ %1").arg(game.rating));
        if (game.playtime !== undefined)
            parts.push(qsTr("%1 min").arg(Math.floor(game.playtime / 60)));
        return parts;
    }
    signal activated
    // A cena só apresenta o carousel. O mapa de foco continua sendo
    // autoridade da LauncherHome; estes sinais transportam a intenção de
    // controle sem duplicar a resolução de vizinhos no tema.
    signal moveRequested(string direction)

    function _safeColor(value, fallback) {
        if (typeof value !== "string")
            return fallback
        const candidate = value.trim()
        return /^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(candidate)
            ? candidate : fallback
    }

    function _externalView(compiledScene) {
        const views = compiledScene && Array.isArray(compiledScene.views)
            ? compiledScene.views : []
        if (views.length === 0)
            return null
        const preferred = String(scene && scene.menuId || "") === "platforms"
            ? "system" : "gamelist"
        for (let i = 0; i < views.length; ++i)
            if (String(views[i].id || "") === preferred)
                return views[i]
        for (let i = 0; i < views.length; ++i)
            if (String(views[i].id || "") === "gamelist")
                return views[i]
        for (let i = 0; i < views.length; ++i)
            if (String(views[i].id || "") === "system")
                return views[i]
        return views[0]
    }

    property bool _mediaCompleted: false
    property string _scheduledMediaOwner: ""
    property string _scheduledMediaSource: ""

    function _scheduleMedia() {
        if (!_mediaCompleted) return
        const source = selectionReady && !highContrast && !reducedMotion ? videoSource : ""
        const owner = source !== "" ? currentFocus + ":" + String(activeTheme.logicalRevision || "") : ""
        if (source === _scheduledMediaSource && owner === _scheduledMediaOwner) return
        _scheduledMediaSource = source
        _scheduledMediaOwner = owner
        videoSelectionDelay.stop()
        _destroyVideo()
        if (source !== "") videoSelectionDelay.start()
    }

    function _destroyVideo() {
        if (videoBackdrop.player !== null) {
            videoBackdrop.player.stop()
            videoBackdrop.player.destroy()
            videoBackdrop.player = null
        }
        videoBackdrop.loadError = ""
    }

    function _loadVideo(source) {
        _destroyVideo()
        if (!visible || !selectionReady || source === "" || highContrast || reducedMotion)
            return
        // QtMultimedia é opcional no host. O objeto é criado dinamicamente para
        // que uma instalação sem o plugin de vídeo mantenha a cena navegável e
        // revele o fanart/capa como fallback, em vez de falhar ao importar QML.
        try {
            const component = Qt.createComponent(Qt.resolvedUrl("../SceneMediaPlayer.qml"))
            if (component.status !== Component.Ready) {
                videoBackdrop.loadError = qsTr("Suporte multimídia indisponível neste contexto.")
                return
            }
            const item = component.createObject(videoBackdrop, {
                source: source, selectionKey: cinema.currentFocus,
                width: videoBackdrop.width, height: videoBackdrop.height
            })
            if (item === null) {
                videoBackdrop.loadError = qsTr("Não foi possível iniciar a mídia selecionada.")
                return
            }
            item.width = Qt.binding(function() { return videoBackdrop.width })
            item.height = Qt.binding(function() { return videoBackdrop.height })
            videoBackdrop.player = item
            videoBackdrop.loadError = ""
        } catch (error) {
            videoBackdrop.player = null
            videoBackdrop.loadError = qsTr("Não foi possível iniciar a mídia selecionada.")
        }
    }

    onVideoSourceChanged: _scheduleMedia()
    onCurrentFocusChanged: _scheduleMedia()
    onSceneChanged: _scheduleMedia()
    Timer {
        id: videoSelectionDelay
        interval: 100
        onTriggered: if (cinema.visible && cinema.selectionReady) cinema._loadVideo(cinema.videoSource)
    }
    onHighContrastChanged: _scheduleMedia()
    onReducedMotionChanged: _scheduleMedia()

    Timer {
        id: clockRefresh
        interval: 30000
        repeat: true
        running: true
        onTriggered: ++cinema.clockTick
    }

    readonly property string metadataText: {
        const game = cinema.selectedGame;
        const parts = [];
        if (game.releaseDate)
            parts.push(String(game.releaseDate).slice(0, 4));
        if (game.genres && game.genres.length)
            parts.push(game.genres.join(" / "));
        if (game.players !== undefined)
            parts.push(qsTr("%1 jogador(es)").arg(game.players));
        if (game.rating !== undefined)
            parts.push(qsTr("Nota %1/100").arg(game.rating));
        if (game.playtime !== undefined)
            parts.push(qsTr("%1 min jogados").arg(Math.floor(game.playtime / 60)));
        return parts.join(" · ");
    }

    Rectangle {
        anchors.fill: parent
        color: cinema.sceneBackgroundColor
    }

    SceneEsdeView {
        objectName: "launcherCinemaXmlScene"
        anchors.fill: parent
        z: 50
        visible: cinema.externalSceneAvailable
        viewData: cinema.externalViewData || ({"id": "", "elements": []})
        runtimeModel: ({
            "items": cinema.scene && Array.isArray(cinema.scene.items) ? cinema.scene.items : [],
            "selectedIndex": Number(cinema.scene && cinema.scene.selected || 0)
        })
        highContrast: cinema.highContrast
        reducedMotion: cinema.reducedMotion
        Accessible.name: qsTr("Cena XML do tema")
    }

    Rectangle {
        visible: cinema.activeTheme.sceneResolutionState === "degraded"
            || cinema.activeTheme.sceneResolutionState === "failed"
        z: 60
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        height: Math.max(72, Math.min(parent.height * 0.25, 160))
        color: cinema.highContrast ? "#000000" : "#182735"
        border.color: cinema.highContrast ? "#ffffff" : cinema.accentColor
        border.width: 2
        radius: 8
        Text {
            id: xmlSceneDiagnostic
            anchors.fill: parent
            anchors.margins: 10
            text: qsTr("A cena XML está incompleta. A navegação continua disponível. %1")
                .arg(String(cinema.activeTheme.sceneDiagnostic || "Revise o tema no Studio."))
            color: cinema.primaryTextColor
            wrapMode: Text.WordWrap
            font.pixelSize: 14 * cinema.textScale
        }
    }
    // O tier balanced mantém a arte como backdrop nativo e reserva o FBO/blur
    // para cinematic. A base e os véus continuam legíveis mesmo sem fanart.
    MediaEffectLayer {
        id: backdrop
        anchors.fill: parent
        visible: cinema.backdropEffects && String(cinema.selectedGame.fanartUrl || "") !== ""
        source: cinema.backdropEffects ? String(cinema.selectedGame.fanartUrl || "") : ""
        decodeSize: Qt.size(Math.ceil(width), Math.ceil(height))
        fillMode: Image.PreserveAspectCrop
        opacity: 0.34
        effects: cinema.contextualEffectStack
    }
    Item {
        id: videoBackdrop
        objectName: "cinemaVideoBackdrop"
        anchors.fill: parent
        z: 0
        property var player: null
        property string loadError: ""
        readonly property bool ready: player !== null && player.ready === true
        visible: ready && !cinema.highContrast && cinema.videoSource !== ""
        opacity: cinema.performanceTier === "cinematic" ? 0.28 : 0
        // A troca de jogo deve descartar o player anterior imediatamente para
        // não manter áudio/vídeo de uma seleção que já perdeu o foco.
        Component.onCompleted: { cinema._mediaCompleted = true; cinema._scheduleMedia() }
    }
    // Véus de leitura: mantém arte como elemento principal, mas protege
    // título, chips e rodapé em capas claras ou sem paleta publicada.
    Rectangle {
        anchors.fill: parent
        color: cinema.sceneBackgroundColor
        opacity: cinema.highContrast ? 1 : 0.48
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(cinema.sceneBackgroundColor.r, cinema.sceneBackgroundColor.g, cinema.sceneBackgroundColor.b, 0.87) }
            GradientStop { position: 0.42; color: Qt.rgba(cinema.sceneBackgroundColor.r, cinema.sceneBackgroundColor.g, cinema.sceneBackgroundColor.b, 0.27) }
            GradientStop { position: 1.0; color: Qt.rgba(cinema.sceneBackgroundColor.r, cinema.sceneBackgroundColor.g, cinema.sceneBackgroundColor.b, 0.81) }
        }
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Math.max(112, parent.height * 0.18)
        color: cinema.sceneBackgroundColor
        opacity: cinema.highContrast ? 1 : 0.58
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(cinema.sceneBackgroundColor.r, cinema.sceneBackgroundColor.g, cinema.sceneBackgroundColor.b, 0.0) }
            GradientStop { position: 1.0; color: Qt.rgba(cinema.sceneBackgroundColor.r, cinema.sceneBackgroundColor.g, cinema.sceneBackgroundColor.b, 0.8) }
        }
    }

    function activateSelection() {
        // Toque só pode ativar uma capa que já corresponde ao foco publicado.
        if (!cinema.selectionReady)
            return false;
        cinema.activated();
        return true;
    }

    function activateFocused() {
        // Teclado/controle representa o foco semântico da Home. Após uma
        // seta, a ponte ainda pode estar atualizando `scene.focusId`; bloquear
        // o Enter nesse intervalo abriria uma janela em que a tela parece
        // navegável, mas o controle não responde. A Home valida o nó e resolve
        // o gameId a partir de `currentFocus`.
        if (cinema.currentFocus === "")
            return false;
        cinema.activated();
        return true;
    }

    Keys.onLeftPressed: cinema.moveRequested("left")
    Keys.onRightPressed: cinema.moveRequested("right")
    Keys.onUpPressed: cinema.moveRequested("up")
    Keys.onDownPressed: cinema.moveRequested("down")
    Keys.onReturnPressed: cinema.activateFocused()
    Keys.onEnterPressed: cinema.activateFocused()
    Keys.onSpacePressed: cinema.activateFocused()
    focus: visible

    Item {
        id: coverViewport
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.topMargin: 16
        anchors.bottom: selectedTitle.top
        anchors.bottomMargin: 16
        clip: true

        Item {
            id: coverCanvas
            anchors.centerIn: parent
            width: cinema.scene && cinema.scene.viewport ? cinema.scene.viewport.width : cinema.width
            height: cinema.scene && cinema.scene.viewport ? cinema.scene.viewport.height : cinema.height
            scale: Math.min(coverViewport.width / Math.max(1, width), Math.max(0, coverViewport.height) / Math.max(1, height))

            SceneRepeater {
                objectName: "cinemaNativeComposition"
                visible: cinema.nativeRecipeLayout && cinema.selectionReady
                anchors.fill: parent
                layout: cinema.activeLayout
                visualScale: cinema.textScale
            }
            Item {
                readonly property var selectedEntry: cinema.entries[Number(cinema.scene && cinema.scene.selected || 0)] || ({})
                visible: cinema.nativeRecipeLayout && cinema.selectionReady
                x: Number(selectedEntry.x || 0)
                y: Number(selectedEntry.y || 0)
                width: Number(selectedEntry.width || 0)
                height: Number(selectedEntry.height || 0)
                scale: Number(selectedEntry.scale || 1)
                z: 100
                Accessible.role: Accessible.Button
                Accessible.name: String(cinema.selectedGame.title || "")
                TapHandler { onTapped: cinema.activateSelection() }
            }
            Repeater {
                model: cinema.nativeRecipeLayout ? [] : cinema.entries
                delegate: Rectangle {
                    id: card
                    objectName: card.modelData.highlighted
                        ? "cinemaSelectedCover" : "cinemaNeighbourCover"
                    required property var modelData
                    required property int index
                    readonly property var game: cinema.scene.items[index] || ({})
                    x: modelData.x
                    y: modelData.y
                    width: modelData.width
                    height: modelData.height
                    scale: modelData.scale
                    opacity: cinema.highContrast ? 1 : modelData.opacity
                    z: modelData.z
                    color: cinema.highContrast ? "#000000" : "#142332"
                    radius: 8
                    border.width: modelData.highlighted ? 3 : 1
                    border.color: modelData.highlighted ? cinema.accentColor : "#667789"
                    Behavior on scale {
                        enabled: !cinema.reducedMotion
                        NumberAnimation { duration: cinema.motionDuration; easing.type: Easing.OutCubic }
                    }
                    Behavior on opacity {
                        enabled: !cinema.reducedMotion
                        NumberAnimation { duration: cinema.motionDuration; easing.type: Easing.OutCubic }
                    }
                    Accessible.name: String(game.title || "")
                    Accessible.role: Accessible.Button
                    Accessible.description: qsTr("Abrir os detalhes do jogo selecionado")
                    MediaEffectLayer {
                        id: cover
                        anchors.fill: parent
                        anchors.margins: 4
                        source: card.modelData.source || ""
                        decodeSize: Qt.size(Math.ceil(width), Math.ceil(height))
                        fillMode: Image.PreserveAspectFit
                        effects: card.modelData.highlighted
                            ? cinema.focusedCoverEffectStack : cinema.peripheralCoverEffectStack
                    }
                    Image {
                        anchors.centerIn: parent
                        width: parent.width * 0.78
                        height: parent.height * 0.28
                        visible: card.modelData.highlighted
                            && String(card.game.logoUrl || "") !== ""
                        source: String(card.game.logoUrl || "")
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        sourceSize: Qt.size(Math.ceil(width * 2), Math.ceil(height * 2))
                        opacity: 0.94
                    }
                    LauncherCoverFallback {
                        objectName: "cinemaCoverFallback"
                        anchors.fill: parent
                        anchors.margins: 4
                        visible: cover.sourceStatus !== Image.Ready
                        title: String(card.game.title || "")
                        // O título do jogo em foco já aparece abaixo do
                        // carrossel; nos vizinhos, sobrepostos, virava texto
                        // cortado.
                        showTitle: card.modelData.highlighted
                        highContrast: cinema.highContrast
                        accentColor: cinema.accentColor
                        textScale: cinema.textScale
                    }
                    TapHandler {
                        enabled: card.modelData.highlighted && cinema.selectionReady
                        onTapped: cinema.activateSelection()
                    }
                }
            }
        }
    }
    Text {
        id: header
        objectName: "cinemaHeader"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 24
        text: String(cinema.activeTheme.themeName || qsTr("Launcher")) + " · "
            + String(cinema.scene ? cinema.scene.collection || "" : "")
        textFormat: Text.PlainText
        width: parent.width - 48
        elide: Text.ElideRight
        color: cinema.primaryTextColor
        font.pixelSize: 18 * cinema.textScale
    }
    Row {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 24
        spacing: 16
        Text {
            objectName: "cinemaConnection"
            text: (cinema.connectionState === "connected" ? "● ONLINE" : "● OFFLINE")
            color: cinema.connectionState === "connected" ? "#7be47f" : "#ff8e94"
            font.pixelSize: 14 * cinema.textScale
            Accessible.name: qsTr("Estado da ponte: %1").arg(text)
        }
        Text {
            objectName: "cinemaClock"
            text: cinema.clockLabel
            color: cinema.primaryTextColor
            font.pixelSize: 18 * cinema.textScale
            font.bold: true
            Accessible.name: qsTr("Hora atual %1").arg(text)
        }
    }
    Text {
        id: selectedTitle
        objectName: "cinemaSelectedTitle"
        anchors.bottom: metadataRail.top
        anchors.bottomMargin: 16
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 48
        text: cinema.selectionReady ? String(cinema.selectedGame.title || "") : qsTr("Atualizando seleção…")
        textFormat: Text.PlainText
        color: cinema.primaryTextColor
        font.pixelSize: 24 * cinema.textScale
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: selectedTitle.top
        anchors.bottomMargin: 8
        width: Math.min(parent.width * 0.28, 320)
        height: 3
        radius: 2
        color: cinema.accentColor
        visible: cinema.selectionReady && !cinema.highContrast
    }
    Item {
        id: metadataRail
        anchors.bottom: footer.top
        anchors.bottomMargin: 12
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 48
        height: 32 * cinema.textScale
        Accessible.name: cinema.selectionReady ? cinema.metadataText : ""
        Row {
            anchors.centerIn: parent
            spacing: 8
            Repeater {
                model: cinema.selectionReady ? cinema.metadataParts : []
                delegate: Rectangle {
                    required property string modelData
                    height: 28 * cinema.textScale
                    width: metadataLabel.implicitWidth + 20 * cinema.textScale
                    radius: height / 2
                    color: cinema.highContrast ? "#000000" : "#071019cc"
                    border.width: 1
                    border.color: cinema.highContrast ? "#ffffff" : "#526779"
                    Text {
                        id: metadataLabel
                        anchors.centerIn: parent
                        text: modelData
                        color: cinema.primaryTextColor
                        font.pixelSize: 12 * cinema.textScale
                    }
                }
            }
        }
    }
    Text {
        id: footer
        objectName: "cinemaFooter"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        text: qsTr("← → Jogos    ↑ ↓ Coleções    Enter Detalhes    F Buscar    Esc Voltar")
        width: parent.width - 48
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        color: cinema.primaryTextColor
        font.pixelSize: 16 * cinema.textScale
    }
}
